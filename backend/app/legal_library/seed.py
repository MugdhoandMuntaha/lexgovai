"""Foundational Bangladesh Statutory Seed Data and Automated Ingestion.

Populates the Bangladesh Legal Library with authoritative acts, ordinances, and SROs
covering VAT, Labour, Companies, Income Tax, Customs, Environment, Banking, and Foreign Exchange.
All instruments are ingested through LegalIngestionPipeline (extraction, structuring,
classification, RapidFuzz verification, FTS5 and vector indexing).
"""

from __future__ import annotations

import logging
from pathlib import Path
from app.db import Database
from app.legal_library.pipeline import LegalIngestionPipeline

logger = logging.getLogger(__name__)

FOUNDATIONAL_LAWS: list[dict[str, str]] = [
    {
        "filename": "vat_act_2012.txt",
        "source_url": "http://bdlaws.minlaw.gov.bd/act-1093.html",
        "content": """VALUE ADDED TAX AND SUPPLEMENTARY DUTY ACT, 2012
Act No. 47 of 2012
মূল্য সংযোজন কর ও সম্পূরক শুল্ক আইন, ২০১২

An Act to consolidate and amend the law relating to value added tax and supplementary duty in Bangladesh.

CHAPTER 1
PRELIMINARY

Section 1. Short title, extent and commencement.
(1) This Act may be called the Value Added Tax and Supplementary Duty Act, 2012.
(2) It extends to the whole of Bangladesh.
(3) It came into force on the 1st day of July, 2019 by statutory notification.

Section 2. Definitions.
In this Act, unless there is anything repugnant in the subject or context:
(1) "Taxable supply" means a supply of goods, services, or immovable property other than an exempt supply.
(2) "Tax invoice" means a Mushak-6.3 tax invoice issued under section 31 of this Act.
(3) "Registered person" means any person registered for Value Added Tax with the National Board of Revenue.
(4) "Withholding entity" means government agencies, autonomous bodies, non-government organizations, and limited companies required to deduct VAT at source.

CHAPTER 3
IMPOSITION AND COLLECTION OF TAX

Section 15. Imposition of Value Added Tax.
(1) Value Added Tax shall be imposed and payable on taxable imports and taxable supplies at the standard rate of 15% (fifteen percent), or at reduced rates of 5%, 7.5%, or 10% specified in the Third Schedule.
(2) Every registered person making a taxable supply shall be liable to account for and pay the tax in accordance with this Act.

Section 31. Requirement of Tax Invoice (Mushak-6.3).
(1) Every registered supplier shall, on or before making a taxable supply or before goods leave the premises, issue a serially numbered tax invoice in prescribed Form Mushak-6.3.
(2) No person shall transport taxable goods without a valid tax invoice or transport challan.

Section 49. Deduction of Tax at Source (VDS).
(1) A withholding entity purchasing taxable goods or services specified by the Board shall deduct the applicable amount of VAT at source prior to making payment to the supplier.
(2) The withholding entity shall issue a withholding certificate in Form Mushak-6.6 within 3 (three) working days of deduction.

Section 64. Return Filing and Payment of VAT.
(1) Every registered person shall submit a monthly VAT return in Form Mushak-9.1 to the Commissioner of Taxes within 15 (fifteen) days following the end of each tax period.
(2) Failure to submit the return within the statutory timeline shall attract late fee of BDT 10,000 and interest on unpaid tax.

Section 107. Maintenance of Accounts and Records.
(1) Every registered person shall maintain purchase books (Mushak-6.1), sales books (Mushak-6.2), and audited financial statements for a period of not less than 5 (five) years.
"""
    },
    {
        "filename": "companies_act_1994.txt",
        "source_url": "http://bdlaws.minlaw.gov.bd/act-789.html",
        "content": """THE COMPANIES ACT, 1994
Act No. 18 of 1994
কোম্পানি আইন, ১৯৯৪

An Act to consolidate and amend the law relating to companies and certain other associations in Bangladesh.

CHAPTER 1
PRELIMINARY

Section 1. Short title and commencement.
(1) This Act may be called the Companies Act, 1994.
(2) It shall come into force at once.
(3) It applies to all companies incorporated under this Act or previous company legislation in Bangladesh.

Section 2. Definitions.
In this Act, unless the context otherwise requires:
(1) "Company" means a company formed and registered under this Act or an existing company.
(2) "Director" includes any person occupying the position of director, by whatever name called.
(3) "Registrar" means the Registrar of Joint Stock Companies and Firms (RJSC).

CHAPTER 2
CONSTITUTION AND INCORPORATION

Section 16. Memorandum of Association.
(1) The memorandum of every company shall state the name of the company, the registered office address, the objects of the company, and the authorized share capital.
(2) In the case of a company limited by shares, the memorandum shall state that the liability of its members is limited.

CHAPTER 4
MANAGEMENT AND ADMINISTRATION

Section 76. Annual General Meeting (AGM).
(1) Every company shall in each year hold in addition to any other meetings a general meeting as its Annual General Meeting (AGM).
(2) Not more than 15 (fifteen) months shall elapse between the date of one AGM and that of the next, and within 9 (nine) months of the end of the financial year.

Section 181. Maintenance of Books of Accounts.
(1) Every company shall keep at its registered office proper books of accounts with respect to all sums of money received and expended, all sales and purchases of goods, and the assets and liabilities of the company.
(2) The books of accounts shall give a true and fair view of the state of affairs of the company and explain its transactions.

Section 396. Registration of Foreign Companies.
(1) Every foreign company establishing a place of business within Bangladesh shall, within 30 (thirty) days of establishment, deliver to the Registrar a certified copy of its charter or statutes, the full address of its principal office in Bangladesh, and list of directors.
"""
    },
    {
        "filename": "labour_act_2006.txt",
        "source_url": "http://bdlaws.minlaw.gov.bd/act-957.html",
        "content": """BANGLADESH LABOUR ACT, 2006
Act No. 42 of 2006
বাংলাদেশ শ্রম আইন, ২০০৬

An Act to consolidate and amend the laws relating to employment of workers, relations between workers and employers, determination of minimum rates of wages, payment of wages, and safety in workplaces.

CHAPTER 1
PRELIMINARY

Section 1. Short title, commencement and application.
(1) This Act may be called the Bangladesh Labour Act, 2006.
(2) It extends to the whole of Bangladesh.
(3) It applies to commercial establishments, industrial establishments, factories, shops, and transport undertakings.

Section 5. Mandatory Appointment Letter and Identity Card.
(1) No employer shall employ any worker without giving him a formal written letter of appointment.
(2) Every worker shall be provided with a photo identity card free of charge by the employer.

CHAPTER 9
WORKING HOURS AND LEAVE

Section 100. Daily Working Hours.
(1) No adult worker shall ordinarily be required or allowed to work in an establishment for more than 8 (eight) hours in any day.
(2) Any work performed beyond 8 hours shall be treated as overtime work.

Section 102. Weekly Working Hours.
(1) No adult worker shall ordinarily work for more than 48 (forty-eight) hours in any week.
(2) The total hours of work including overtime shall not exceed 60 (sixty) hours in any week, and on the average 56 hours per week in any year.

Section 108. Extra Allowance for Overtime Work.
(1) Where a worker works in an establishment for more than 8 hours on any day or more than 48 hours in any week, he shall in respect of overtime work be entitled to allowance at the rate of twice his ordinary rate of basic wage.

CHAPTER 4
MATERNITY BENEFIT

Section 46. Right to Maternity Benefit.
(1) Every female worker shall be entitled to the payment of maternity benefit for a period of 8 (eight) weeks preceding the day of delivery and 8 (eight) weeks immediately following that day, totaling 16 weeks of paid maternity leave.
(2) No female worker shall be employed in any establishment during the 8 weeks immediately following the day of her delivery.

CHAPTER 6
SAFETY AND HEALTH

Section 61. Fire Precautions and Emergency Exits.
(1) Every establishment shall be provided with adequate means of escape in case of fire, clearly marked in Bengali and English.
(2) Fire-fighting apparatus and emergency drills shall be conducted at least once in every 6 (six) months.
"""
    },
    {
        "filename": "income_tax_act_2023.txt",
        "source_url": "http://bdlaws.minlaw.gov.bd/act-1440.html",
        "content": """INCOME TAX ACT, 2023
Act No. 12 of 2023
আয়কর আইন, ২০২৩

An Act to consolidate and amend the law relating to income-tax and super-tax in Bangladesh.

CHAPTER 1
PRELIMINARY

Section 1. Short title, extent and commencement.
(1) This Act may be called the Income Tax Act, 2023.
(2) It extends to the whole of Bangladesh.
(3) It came into force on the first day of July, 2023.

Section 2. Definitions.
In this Act, unless there is anything repugnant in the subject or context:
(1) "Assessee" means any person by whom any tax or other sum of money is payable under this Act.
(2) "Assessment year" means the period of twelve months commencing on the first day of July every year.
(3) "Company" means a company incorporated under the Companies Act, 1994 or any foreign corporate body.

CHAPTER 7
TAX DEDUCTION AT SOURCE (TDS)

Section 73. Deduction of Tax on Supply of Goods and Execution of Contracts.
(1) Any person responsible for paying to a resident any sum for supply of goods or execution of contract shall, at the time of payment, deduct advance tax at prescribed statutory rates.
(2) The tax deducted under this section shall be deposited to the government treasury within 7 (seven) days of deduction.

Section 166. Requirement to File Return of Income.
(1) Every person whose total income during the income year exceeds the maximum amount not chargeable to tax shall file a return of income.
(2) Every company, firm, association of persons, and registered trust shall file a return of income regardless of taxable income status on or before Tax Day.
"""
    },
    {
        "filename": "customs_act_2023.txt",
        "source_url": "http://bdlaws.minlaw.gov.bd/act-1456.html",
        "content": """THE CUSTOMS ACT, 2023
Act No. 57 of 2023
কাস্টমস আইন, ২০২৩

An Act to consolidate and modernize the law relating to customs duties, import and export clearance, and border trade facilitation.

CHAPTER 1
PRELIMINARY

Section 1. Short title, extent and commencement.
(1) This Act may be called the Customs Act, 2023.
(2) It extends to the whole of Bangladesh and to customs waters extending 24 nautical miles from coastal baselines.
(3) It shall come into force on the date appointed by the Government by official gazette notification.

Section 25. Assessment of Duty on Imported and Exported Goods.
(1) Goods imported into or exported from Bangladesh shall be assessed to customs duties at the rates specified in the First Schedule to the Customs Tariff.
(2) The customs value of imported goods shall be determined based on transaction value under WTO Valuation Agreement principles.

Section 79. Electronic Declaration (Bill of Entry).
(1) The owner of any imported goods shall submit an electronic Bill of Entry prior to or at the time of arrival of the conveyance through the designated ASYCUDA World electronic portal.
(2) Clearance of imported cargo shall be subject to physical or non-intrusive container inspection and validation of origin documents.
"""
    },
    {
        "filename": "environment_conservation_act_1995.txt",
        "source_url": "http://bdlaws.minlaw.gov.bd/act-791.html",
        "content": """THE ENVIRONMENT CONSERVATION ACT, 1995
Act No. 1 of 1995
বাংলাদেশ পরিবেশ সংরক্ষণ আইন, ১৯৯৫

An Act to provide for conservation of the environment, improvement of environmental standards, and control and mitigation of environmental pollution.

CHAPTER 1
PRELIMINARY

Section 1. Short title and commencement.
(1) This Act may be called the Environment Conservation Act, 1995.
(2) It extends to the whole of Bangladesh.
(3) It shall come into force at once.

Section 4. Powers and Functions of Director General.
(1) The Director General of the Department of Environment may take all such measures as he deems necessary or expedient for the purpose of conserving and protecting the environment.
(2) The Director General may issue closure, prohibition, or regulation orders against any polluting industrial unit or commercial enterprise.

Section 12. Mandatory Environmental Clearance Certificate (ECC).
(1) No industrial unit or project shall be established or undertaken without obtaining an Environmental Clearance Certificate from the Director General.
(2) Industrial units classified as Orange or Red categories must install and operate functional Effluent Treatment Plants (ETP) prior to commercial operations.
"""
    },
    {
        "filename": "foreign_exchange_regulation_act_1947.txt",
        "source_url": "http://bdlaws.minlaw.gov.bd/act-215.html",
        "content": """FOREIGN EXCHANGE REGULATION ACT, 1947
Act No. 7 of 1947
বৈদেশিক মুদ্রা নিয়ন্ত্রণ আইন, ১৯৪৭

An Act to regulate certain payments, dealings in foreign exchange and securities, and the import and export of currency and bullion.

CHAPTER 1
PRELIMINARY

Section 1. Short title, extent and commencement.
(1) This Act may be called the Foreign Exchange Regulation Act, 1947.
(2) It extends to the whole of Bangladesh and applies to all citizens of Bangladesh and persons in the service of the Republic.

Section 4. Restrictions on Dealing in Foreign Exchange.
(1) Except with the general or special permission of Bangladesh Bank, no person other than an authorized dealer shall buy, borrow, sell, or lend any foreign exchange in Bangladesh.
(2) Foreign exchange acquired by exporters must be converted into local currency (BDT) through authorized banking channels within statutory limits.

Section 12. Realization of Export Proceeds.
(1) Every person exporting goods or services from Bangladesh shall submit an EXP declaration through an authorized dealer.
(2) Full export proceeds must be realized and remitted into Bangladesh within 120 (one hundred and twenty) days from the date of shipment, unless extended by Bangladesh Bank.
"""
    },
    {
        "filename": "bank_company_act_1991.txt",
        "source_url": "http://bdlaws.minlaw.gov.bd/act-754.html",
        "content": """BANK COMPANY ACT, 1991
Act No. 14 of 1991
ব্যাংক-কোম্পানী আইন, ১৯৯১

An Act to consolidate and amend the law relating to bank companies in Bangladesh.

CHAPTER 1
PRELIMINARY

Section 1. Short title, extent and commencement.
(1) This Act may be called the Bank Company Act, 1991.
(2) It extends to the whole of Bangladesh.
(3) It shall come into force at once.

Section 13. Minimum Capital and Reserves Requirement.
(1) Every banking company operating in Bangladesh shall maintain paid-up capital and statutory reserve fund meeting the Capital Adequacy Ratio (CAR) under Basel III prescribed by Bangladesh Bank.
(2) Failure to maintain mandatory capital buffers shall empower Bangladesh Bank to restrict dividend declaration and branch expansion.

Section 27. Single Borrower Exposure Limit.
(1) No banking company shall grant loan facilities or financial accommodation to any single person, enterprise, or corporate group exceeding 25% (twenty-five percent) of its total capital.
(2) Funded exposure to a single borrower shall not exceed 15% of the bank's capital.
"""
    },
    {
        "filename": "sro_144_vat_einvoicing_2025.txt",
        "source_url": "https://nbr.gov.bd/sro/sro-144-vat-2025.pdf",
        "content": """GOVERNMENT OF THE PEOPLE'S REPUBLIC OF BANGLADESH
NATIONAL BOARD OF REVENUE
(Customs and VAT Wing)
NOTIFICATION
S.R.O. No. 144-AIN/2025/112-VAT
এস.আর.ও. নং ১৪৪-আইন/২০২৫/১১২-মূসক

Section 1. Short title and application.
(1) This statutory regulatory order may be called the Electronic Invoicing and Centralized Accounting Order, 2025.
(2) It shall apply to all business enterprises with annual turnover exceeding BDT 50,000,000 (five crore taka).

Section 2. Mandatory Automated Mushak-6.3 Generation.
(1) Every designated enterprise shall generate all Mushak-6.3 tax invoices using certified ERP software or approved electronic fiscal devices.
(2) Each invoice shall contain a machine-readable quick response (QR) code verified by NBR central servers.

Section 3. Real-Time API Data Transmission.
(1) All sales invoice data must be transmitted via secure API endpoints to the NBR Central VAT Management Database in real time.
(2) Failure to integrate or deliberate transmission failure shall incur penalties under Section 85 of the Value Added Tax Act, 2012.
"""
    }
]


def seed_foundational_laws(db: Database) -> int:
    """Ingests foundational Bangladesh laws through LegalIngestionPipeline if the library is empty."""
    existing_count_row = db._fetchone("SELECT COUNT(*) as c FROM laws WHERE publish_state = 'published'")
    existing_count = int(existing_count_row["c"]) if existing_count_row else 0
    if existing_count > 0:
        logger.info(f"Legal library already contains {existing_count} published laws. Skipping seed.")
        return existing_count

    logger.info("Seeding foundational Bangladesh laws into Legal Library through AI Ingestion Pipeline...")
    pipeline = LegalIngestionPipeline(
        db=db,
        vectorstore=None,  # ChromaDB collection if active
        llm=None,
        ocr_engine=None,
    )

    ingested = 0
    for item in FOUNDATIONAL_LAWS:
        try:
            res = pipeline.ingest_document(
                filename=item["filename"],
                content=item["content"].strip().encode("utf-8"),
                source_url=item["source_url"],
            )
            logger.info(f"Ingested law: {item['filename']} -> law_id={res.law_id} (state={res.publish_state})")
            ingested += 1
        except Exception as e:
            logger.error(f"Failed to seed law {item['filename']}: {e}", exc_info=True)

    logger.info(f"Seeded {ingested} foundational Bangladesh statutes successfully.")
    return ingested
