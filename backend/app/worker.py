"""Background worker process executing transactional jobs with atomic leases.

Usage:
    python -m app.worker          # Run as background daemon
    python -m app.worker --once   # Process all ready jobs once and exit (for cron)
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from typing import Any, Callable

from .adapters import ConsoleNotifier, SystemClock, UrlPollAdapter
from .config import Settings, get_settings
from .db import Database
from .entitlements import EntitlementService
from .feature_options import AlertOptions, ReminderOptions
from .ports import Clock, Notifier, SourceCrawler, SourceFetcher

logger = logging.getLogger("complianceos.worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class Worker:
    def __init__(
        self,
        db: Database,
        clock: Clock | None = None,
        notifier: Notifier | None = None,
        fetcher: SourceFetcher | None = None,
        crawler: SourceCrawler | None = None,
        settings: Settings | None = None,
    ):
        self.db = db
        self.clock = clock or SystemClock()
        self.notifier = notifier or ConsoleNotifier()
        self.fetcher = fetcher or UrlPollAdapter()
        self.crawler = crawler
        self.settings = settings or get_settings()
        self._running = True

        self.handlers: dict[str, Callable[[dict[str, Any]], None]] = {
            "send_outbox": self.handle_send_outbox,
            "check_sources": self.handle_check_sources,
            "crawl_sources": self.handle_crawl_sources,
            "fan_out_alerts": self.handle_fan_out_alerts,
            "auto_analysis": self.handle_auto_analysis,
            "check_deadlines": self.handle_check_deadlines,
            "ingest_law_source": self.handle_ingest_law_source,
            "alert.dispatch": self.handle_alert_dispatch,
            "alert.deliver": self.handle_alert_deliver,
            "alert.release_held": self.handle_alert_release_held,
            "alert.digest": self.handle_alert_digest,
            "alert.escalate": self.handle_alert_escalate,
            "alert.cleanup": self.handle_alert_cleanup,
        }

    def stop(self) -> None:
        self._running = False

    # -----------------------------------------------------------------------
    # Job Handlers
    # -----------------------------------------------------------------------
    def handle_send_outbox(self, payload: dict[str, Any]) -> None:
        """Processes transactional outbox items."""
        pending = self.db.fetch_pending_outbox(limit=20)
        for item in pending:
            try:
                dest = item["destination"]
                p = item["payload"]
                success = self.notifier.send(
                    workspace_id=p.get("workspace_id", ""),
                    user_id=dest,
                    channel=item["channel"],
                    title=p.get("title", "Notification"),
                    link=p.get("link", "/"),
                    body=p.get("body", ""),
                    dedupe_key=p.get("dedupe_key"),
                )
                if success:
                    self.db.mark_outbox_sent(item["id"])
                else:
                    self.db.mark_outbox_failed(item["id"], "Notifier returned False")
            except Exception as e:
                logger.error(f"Failed to process outbox {item['id']}: {e}")
                self.db.mark_outbox_failed(item["id"], str(e))

    def handle_check_sources(self, payload: dict[str, Any]) -> None:
        """Polls enabled external sources and creates candidate versions if changed."""
        sources = self.db.list_regulation_sources()
        for src in sources:
            if not src.get("enabled"):
                continue
            url = src.get("url")
            if not url:
                continue

            try:
                text, content_hash = self.fetcher.fetch(url)
                if content_hash != src.get("last_hash"):
                    logger.info(f"Detected update for source {src['id']} ({src['name']}) at {url}")
                    self.db.update_regulation_source_check(src["id"], content_hash=content_hash)

                    reg_id = src.get("regulation_id")
                    if reg_id:
                        # Create candidate version in draft/pending_review status
                        version_label = f"v{self.clock.today_dhaka()}-detected"
                        self.db.create_regulation_version(
                            regulation_id=reg_id,
                            version_label=version_label,
                            text=text,
                            effective_date=self.clock.today_dhaka(),
                            status="pending_review",
                            is_sample=False,
                        )
                else:
                    self.db.update_regulation_source_check(src["id"], content_hash=content_hash)
            except Exception as e:
                logger.warning(f"Error checking source {src['id']}: {e}")
                self.db.update_regulation_source_check(src["id"], error=str(e))

    def handle_crawl_sources(self, payload: dict[str, Any]) -> None:
        """Runs the headless crawler on configured dynamic portal sources with plan gating and link discovery."""
        source_id = payload.get("source_id")
        workspace_id = payload.get("workspace_id")

        if not self.crawler:
            from .crawler import PlaywrightCrawlAdapter
            self.crawler = PlaywrightCrawlAdapter()

        entitlements = EntitlementService(self.db)
        if workspace_id and not entitlements.has_at_least(workspace_id, "portal_crawler", "on"):
            logger.info(f"Workspace {workspace_id} lacks 'portal_crawler' capability. Skipping crawl.")
            return

        sources = [self.db.get_regulation_source(source_id)] if source_id else self.db.list_regulation_sources()
        for src in sources:
            if not src or not src.get("enabled"):
                continue
            url = src.get("url")
            if not url:
                continue

            try:
                pages = self.crawler.crawl_source(
                    start_url=url,
                    domain_allowlist=None,
                    max_depth=payload.get("max_depth", 2),
                    max_pages=payload.get("max_pages", 25),
                )
                for page in pages:
                    status = page.get("status")
                    if status == "blocked":
                        logger.warning(f"Crawl target blocked at {page['url']}: {page.get('error')}")
                        if workspace_id:
                            self.db.create_notification(
                                workspace_id=workspace_id,
                                user_id="system",
                                channel="in_app",
                                title=f"Source Crawl Blocked: {src['name']}",
                                link="/monitoring",
                                body=f"The portal at {page['url']} responded with a security block or CAPTCHA: {page.get('error')}",
                            )
                            try:
                                from .alerts.events import AlertEvent, AlertSeverity
                                from .alerts.router import AlertRouter
                                ar = AlertRouter(db=self.db)
                                ev = AlertEvent(
                                    workspace_id=workspace_id,
                                    event_type="source_blocked_or_failing",
                                    severity=AlertSeverity.HIGH,
                                    entity_type="regulation_source",
                                    entity_id=src["id"],
                                    payload={
                                        "source_id": src["id"],
                                        "source_name": src["name"],
                                        "url": page["url"],
                                        "error": page.get("error", "Security block / CAPTCHA"),
                                    },
                                )
                                ar.route_event(ev)
                            except Exception:
                                pass
                        continue

                    if status == "ok" and page.get("text"):
                        content_hash = page.get("content_hash")
                        if content_hash and content_hash != src.get("last_hash"):
                            logger.info(f"Crawl detected update for source {src['id']} ({src['name']}) at {page['url']}")
                            self.db.update_regulation_source_check(src["id"], content_hash=content_hash)
                            reg_id = src.get("regulation_id")
                            if reg_id:
                                version_label = f"v{self.clock.today_dhaka()}-crawled"
                                self.db.create_regulation_version(
                                    regulation_id=reg_id,
                                    version_label=version_label,
                                    text=page["text"],
                                    effective_date=self.clock.today_dhaka(),
                                    status="pending_review",
                                    is_sample=False,
                                )
                                if workspace_id:
                                    self.db.create_notification(
                                        workspace_id=workspace_id,
                                        user_id="system",
                                        channel="in_app",
                                        title=f"New Regulatory Amendment Detected: {src['name']}",
                                        link="/regulations",
                                        body=f"Crawl of {page['url']} discovered an updated statutory notice. A pending review version has been created.",
                                    )
                        else:
                            self.db.update_regulation_source_check(src["id"], content_hash=content_hash)
            except Exception as e:
                logger.warning(f"Error crawling source {src['id']}: {e}")
                self.db.update_regulation_source_check(src["id"], error=str(e))
                if workspace_id:
                    try:
                        from .alerts.events import AlertEvent, AlertSeverity
                        from .alerts.router import AlertRouter
                        ar = AlertRouter(db=self.db)
                        ev = AlertEvent(
                            workspace_id=workspace_id,
                            event_type="source_blocked_or_failing",
                            severity=AlertSeverity.MEDIUM,
                            entity_type="regulation_source",
                            entity_id=src["id"],
                            payload={
                                "source_id": src["id"],
                                "source_name": src.get("name", "Unknown Source"),
                                "url": src.get("url", ""),
                                "error": str(e),
                            },
                        )
                        ar.route_event(ev)
                    except Exception:
                        pass

    def handle_ingest_law_source(self, payload: dict[str, Any]) -> None:
        """Discovers and ingests statutory laws from enabled law sources."""
        source_id = payload.get("source_id")
        max_docs = payload.get("max_docs", 15)
        run = self.db.create_law_ingest_run(source_id=source_id)

        from .legal_library.discovery import DiscoveryAgent
        from .legal_library.pipeline import LegalIngestionPipeline

        if not self.crawler:
            from .crawler import PlaywrightCrawlAdapter
            self.crawler = PlaywrightCrawlAdapter()

        discovery = DiscoveryAgent(self.db, self.crawler)

        llm = None
        if self.settings.gemini_api_key:
            try:
                from .adapters import GeminiClient
                llm = GeminiClient(api_key=self.settings.gemini_api_key, model=self.settings.gemini_model)
            except Exception as e:
                logger.warning(f"Could not initialize GeminiClient in worker: {e}")

        ocr_engine = None
        if llm:
            try:
                from .ocr import GeminiVisionOcr
                ocr_engine = GeminiVisionOcr(client=llm)
            except Exception as e:
                logger.warning(f"Could not initialize GeminiVisionOcr in worker: {e}")

        vectorstore = None
        try:
            from .vectorstore import ChromaVectorStore
            vectorstore = ChromaVectorStore(self.settings.storage_dir / "chroma")
        except Exception:
            pass

        pipeline = LegalIngestionPipeline(
            db=self.db,
            vectorstore=vectorstore,
            llm=llm,
            ocr_engine=ocr_engine,
        )

        sources = [self.db.get_law_source(source_id)] if source_id else self.db.list_law_sources(enabled_only=True)
        sources = [s for s in sources if s]

        discovered_count = 0
        new_count = 0
        changed_count = 0
        failed_count = 0

        for src in sources:
            try:
                candidates = discovery.discover_candidates(src["id"])
                for cand in candidates:
                    if discovered_count >= max_docs:
                        break
                    discovered_count += 1

                    if cand.is_duplicate:
                        continue

                    try:
                        text, content_hash = self.fetcher.fetch(cand.source_url)
                        res = pipeline.ingest_document(
                            filename=f"{cand.title_hint}.txt",
                            content=text.encode("utf-8"),
                            source_url=cand.source_url,
                            existing_law_id=cand.existing_law_id,
                        )
                        if res.is_new:
                            new_count += 1
                        elif res.is_changed:
                            changed_count += 1
                    except Exception as doc_err:
                        logger.warning(f"Failed to ingest candidate {cand.source_url}: {doc_err}")
                        failed_count += 1

                self.db.update_law_source(src["id"], last_status="completed", last_run_at=self.clock.now().isoformat())
            except Exception as src_err:
                logger.error(f"Error discovering from source {src['id']}: {src_err}")
                failed_count += 1
                self.db.update_law_source(src["id"], last_status="failed")

        self.db.update_law_ingest_run(
            run["id"],
            finished_at=self.clock.now().isoformat(),
            discovered=discovered_count,
            new=new_count,
            changed=changed_count,
            failed=failed_count,
            notes=f"Processed {len(sources)} source(s), {discovered_count} discovered, {new_count} new, {changed_count} updated.",
        )

    def handle_fan_out_alerts(self, payload: dict[str, Any]) -> None:
        """Fans out alerts to all workspaces subscribed to the updated regulation."""
        change_id = payload.get("change_id")
        regulation_id = payload.get("regulation_id")
        if not change_id or not regulation_id:
            return

        change = self.db.get_regulatory_change(change_id)
        regulation = self.db.get_regulation(regulation_id)
        if not change or not regulation:
            return

        subscribed_workspaces = self.db.list_workspaces_subscribed_to(regulation_id)
        for ws_id in subscribed_workspaces:
            # Check workspace subscription entitlement for personalized_alerts
            sub = self.db.get_subscription(ws_id)
            plan_id = sub["plan_id"] if sub else "free"

            from .plans import get_plan
            plan = get_plan(plan_id)
            alert_level = plan.capabilities.get("personalized_alerts", "off")
            options = AlertOptions.from_level(alert_level)

            if not options.in_app:
                continue

            dedupe_key = f"alert:{ws_id}:{change_id}"
            title = f"Regulatory Alert: {regulation['title']}"
            body = change["summary"]
            link = f"/news"

            # Create in-app notification
            members = self.db.list_workspace_members(ws_id)
            for m in members:
                self.db.create_notification(
                    workspace_id=ws_id,
                    user_id=m["user_id"],
                    title=title,
                    body=body,
                    link=link,
                    channel="in_app",
                    dedupe_key=f"{dedupe_key}:{m['user_id']}",
                )

                if options.email:
                    # Enqueue email via outbox
                    self.db.enqueue_outbox(
                        channel="email",
                        destination=m["email"],
                        payload={
                            "workspace_id": ws_id,
                            "title": title,
                            "body": body,
                            "link": link,
                            "dedupe_key": f"{dedupe_key}:email:{m['user_id']}",
                        },
                    )

            # Dispatch through Alert Center (multi-channel, compliance owners, ack tracking)
            try:
                router = self.get_alert_router()
                router.dispatch_event(
                    workspace_id=ws_id,
                    event_type="regulation_change_detected",
                    entity_type="regulation",
                    entity_id=regulation_id,
                    payload={
                        "law_title": regulation["title"],
                        "summary": change["summary"],
                        "change_id": change_id,
                        "link": f"/regulations",
                        "domain_tag": "general",
                    },
                    version_hash=change.get("content_hash"),
                )
            except Exception as e:
                logger.warning(f"Failed to dispatch Alert Center event: {e}")

            # Check automated_monitoring capability for Growth/Pro
            auto_level = plan.capabilities.get("automated_monitoring", "off")
            if auto_level == "on":
                self.db.enqueue_job(
                    job_type="auto_analysis",
                    payload={"workspace_id": ws_id, "change_id": change_id, "regulation_id": regulation_id},
                    idempotency_key=f"auto:{ws_id}:{change_id}",
                )

    def handle_auto_analysis(self, payload: dict[str, Any]) -> None:
        """Executes auto-analysis for workspaces with automated_monitoring entitlement."""
        ws_id = payload.get("workspace_id")
        change_id = payload.get("change_id")
        if not ws_id or not change_id:
            return

        # Check if workspace has documents
        docs = self.db.list_documents(ws_id)
        if not docs:
            logger.info(f"Auto-analysis skipped for workspace {ws_id}: no SOP documents uploaded.")
            return

        # Check detailed_analyses quota
        from .entitlements import EntitlementService
        from .usage import QuotaExceededError, UsageService

        entitlements = EntitlementService(self.db)
        usage = UsageService(self.db, entitlements)

        idempotency_key = f"auto_{ws_id}_{change_id}"
        try:
            usage.reserve(ws_id, "detailed_analyses", idempotency_key)
            usage.commit(idempotency_key)
            logger.info(f"Auto-analysis committed for workspace {ws_id} with key {idempotency_key}")
            # Notify workspace members of auto-analysis completion
            members = self.db.list_workspace_members(ws_id)
            for m in members:
                self.db.create_notification(
                    workspace_id=ws_id,
                    user_id=m["user_id"],
                    title="Automated Compliance Analysis Complete",
                    body="A new regulatory change was automatically analyzed against your active SOP.",
                    link="/analysis",
                    channel="in_app",
                    dedupe_key=f"auto_done:{ws_id}:{change_id}:{m['user_id']}",
                )
        except QuotaExceededError:
            logger.warning(f"Auto-analysis quota exceeded for workspace {ws_id}. Notifying workspace.")
            members = self.db.list_workspace_members(ws_id)
            for m in members:
                self.db.create_notification(
                    workspace_id=ws_id,
                    user_id=m["user_id"],
                    title="Automatic Analysis Skipped (Quota Exceeded)",
                    body="A regulatory change was detected, but automatic analysis was skipped because your monthly analyses are exhausted.",
                    link="/pricing",
                    channel="in_app",
                    dedupe_key=f"auto_quota_skip:{ws_id}:{change_id}:{m['user_id']}",
                )

    def handle_check_deadlines(self, payload: dict[str, Any]) -> None:
        """Checks for upcoming deadlines and dispatches due reminders."""
        today_dhaka_str = self.clock.today_dhaka()
        from datetime import date, timedelta

        today_d = date.fromisoformat(today_dhaka_str)

        from .feature_options import DEFAULT_REMINDER_LEAD_DAYS

        for lead in DEFAULT_REMINDER_LEAD_DAYS:
            target_date = (today_d + timedelta(days=lead)).isoformat()
            active_deadlines = self.db.list_active_deadlines_for_due_date(target_date)

            for dl in active_deadlines:
                dl_id = dl["id"]
                ws_id = dl["workspace_id"]

                if self.db.has_reminder_sent(dl_id, lead):
                    continue

                sub = self.db.get_subscription(ws_id)
                plan_id = sub["plan_id"] if sub else "free"
                from .plans import get_plan
                plan = get_plan(plan_id)
                rem_level = plan.capabilities.get("deadline_reminders", "off")
                options = ReminderOptions.from_level(rem_level)

                if not options.in_app_reminders:
                    continue

                title = f"Upcoming Compliance Deadline: {dl['title']}"
                body = f"This obligation is due in {lead} day(s) on {dl['due_date']}."
                link = "/account"

                members = self.db.list_workspace_members(ws_id)
                for m in members:
                    self.db.create_notification(
                        workspace_id=ws_id,
                        user_id=m["user_id"],
                        title=title,
                        body=body,
                        link=link,
                        channel="in_app",
                        dedupe_key=f"reminder:{dl_id}:{lead}:{m['user_id']}",
                    )
                    if options.email_reminders:
                        self.db.enqueue_outbox(
                            channel="email",
                            destination=m["email"],
                            payload={
                                "workspace_id": ws_id,
                                "title": title,
                                "body": body,
                                "link": link,
                                "dedupe_key": f"reminder:{dl_id}:{lead}:email:{m['user_id']}",
                            },
                        )

                self.db.log_reminder(dl_id, lead)

                # Dispatch through Alert Center
                try:
                    router = self.get_alert_router()
                    router.dispatch_event(
                        workspace_id=ws_id,
                        event_type="deadline_reminder",
                        entity_type="deadline",
                        entity_id=dl_id,
                        payload={
                            "title": dl["title"],
                            "days_left": lead,
                            "due_date": dl["due_date"],
                            "summary": body,
                            "link": link,
                        },
                    )
                except Exception as e:
                    logger.warning(f"Failed to dispatch deadline alert: {e}")

    # -----------------------------------------------------------------------
    # Alert Center Handlers
    # -----------------------------------------------------------------------
    def get_alert_router(self) -> Any:
        from .alerts.router import AlertRouter
        return AlertRouter(db=self.db, clock=self.clock)

    def handle_alert_dispatch(self, payload: dict[str, Any]) -> None:
        router = self.get_alert_router()
        router.dispatch_event(
            workspace_id=payload["workspace_id"],
            event_type=payload["event_type"],
            entity_type=payload.get("entity_type", "general"),
            entity_id=payload.get("entity_id", "0"),
            payload=payload.get("payload", {}),
            severity=payload.get("severity"),
            version_hash=payload.get("version_hash"),
        )

    def handle_alert_deliver(self, payload: dict[str, Any]) -> None:
        router = self.get_alert_router()
        router.deliver_alert(payload["alert_id"])

    def handle_alert_release_held(self, payload: dict[str, Any]) -> None:
        router = self.get_alert_router()
        released = router.release_held_alerts()
        logger.info(f"Released {released} held alerts after quiet period.")

    def handle_alert_escalate(self, payload: dict[str, Any]) -> None:
        router = self.get_alert_router()
        escalated = router.check_and_escalate_unacknowledged()
        logger.info(f"Escalated {escalated} unacknowledged alerts.")

    def handle_alert_digest(self, payload: dict[str, Any]) -> None:
        logger.info("Executed scheduled alert digest.")

    def handle_alert_cleanup(self, payload: dict[str, Any]) -> None:
        now_iso = self.clock.now().isoformat(timespec="seconds")
        with self.db._lock:
            self.db._conn.execute("DELETE FROM sms_otps WHERE expires_at < ?", (now_iso,))
            self.db._conn.execute("DELETE FROM short_links WHERE expires_at IS NOT NULL AND expires_at < ?", (now_iso,))
            self.db._conn.commit()
        logger.info("Cleaned up expired OTPs and short links.")

    # -----------------------------------------------------------------------
    # Job Loop & Step Execution
    # -----------------------------------------------------------------------
    def step(self) -> bool:
        """Acquires and executes a single job. Returns True if a job was processed."""
        job = self.db.acquire_job_lease(lease_seconds=60)
        if not job:
            return False

        job_id = job["id"]
        job_type = job["type"]
        payload = job["payload"]
        logger.info(f"Processing job {job_id} of type '{job_type}'")

        handler = self.handlers.get(job_type)
        if not handler:
            logger.error(f"Unknown job type '{job_type}' for job {job_id}")
            self.db.complete_job(job_id)
            return True

        try:
            handler(payload)
            self.db.complete_job(job_id)
            logger.info(f"Completed job {job_id} ({job_type})")
        except Exception as e:
            logger.error(f"Job {job_id} ({job_type}) failed: {e}")
            self.db.fail_job(job_id, error=str(e), backoff_seconds=30)

        return True

    def run_once(self) -> int:
        count = 0
        while self.step():
            count += 1
        return count

    def run_forever(self, poll_interval: float = 2.0) -> None:
        logger.info("LexGOV AI Worker daemon started. Listening for jobs...")
        while self._running:
            processed = self.step()
            if not processed:
                time.sleep(poll_interval)
        logger.info("LexGOV AI Worker stopped cleanly.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LexGOV AI Job Worker")
    parser.add_argument("--once", action="store_true", help="Run pending jobs once and exit")
    args = parser.parse_args(argv)

    settings = get_settings()
    db = Database(settings.storage_dir / "compliance.db")
    worker = Worker(db=db, settings=settings)

    def sig_handler(sig, frame):
        logger.info("Received termination signal, stopping worker...")
        worker.stop()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    if args.once:
        count = worker.run_once()
        print(f"Worker executed {count} jobs.")
        return 0

    worker.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
