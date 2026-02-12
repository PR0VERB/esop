"""
Management command to seed the JSECompany table with JSE-listed companies.

Usage:
    python manage.py seed_jse_companies          # Seed all
    python manage.py seed_jse_companies --clear   # Clear and re-seed
"""

import logging

from django.core.management.base import BaseCommand

from apps.integrations.models import JSECompany

logger = logging.getLogger(__name__)

# JSE-listed companies (Top 40 + broader market coverage)
# Source: JSE Limited official listings
JSE_COMPANIES = [
    # Top 40 / Large Cap
    {"ticker": "AGL", "company_name": "Anglo American plc", "isin": "GB00B1XZS820", "sector": "Mining", "market_cap_category": "Large Cap"},
    {"ticker": "AMS", "company_name": "Anglo American Platinum Limited", "isin": "ZAE000013181", "sector": "Mining", "market_cap_category": "Large Cap"},
    {"ticker": "ANG", "company_name": "AngloGold Ashanti Limited", "isin": "ZAE000043485", "sector": "Mining", "market_cap_category": "Large Cap"},
    {"ticker": "ANH", "company_name": "Anheuser-Busch InBev SA/NV", "isin": "BE0974293251", "sector": "Consumer Goods", "market_cap_category": "Large Cap"},
    {"ticker": "BHP", "company_name": "BHP Group Limited", "isin": "AU000000BHP4", "sector": "Mining", "market_cap_category": "Large Cap"},
    {"ticker": "BID", "company_name": "Bid Corporation Limited", "isin": "ZAE000216537", "sector": "Consumer Services", "market_cap_category": "Large Cap"},
    {"ticker": "BTI", "company_name": "British American Tobacco plc", "isin": "GB0002875804", "sector": "Consumer Goods", "market_cap_category": "Large Cap"},
    {"ticker": "BVT", "company_name": "Bidvest Group Limited", "isin": "ZAE000117321", "sector": "Industrials", "market_cap_category": "Large Cap"},
    {"ticker": "CFR", "company_name": "Compagnie Financiere Richemont SA", "isin": "CH0210483332", "sector": "Consumer Goods", "market_cap_category": "Large Cap"},
    {"ticker": "CLS", "company_name": "Clicks Group Limited", "isin": "ZAE000134854", "sector": "Consumer Services", "market_cap_category": "Large Cap"},
    {"ticker": "CPI", "company_name": "Capitec Bank Holdings Limited", "isin": "ZAE000035861", "sector": "Financial Services", "market_cap_category": "Large Cap"},
    {"ticker": "DSY", "company_name": "Discovery Limited", "isin": "ZAE000022331", "sector": "Financial Services", "market_cap_category": "Large Cap"},
    {"ticker": "EXX", "company_name": "Exxaro Resources Limited", "isin": "ZAE000084992", "sector": "Mining", "market_cap_category": "Large Cap"},
    {"ticker": "FSR", "company_name": "FirstRand Limited", "isin": "ZAE000066304", "sector": "Financial Services", "market_cap_category": "Large Cap"},
    {"ticker": "GFI", "company_name": "Gold Fields Limited", "isin": "ZAE000018123", "sector": "Mining", "market_cap_category": "Large Cap"},
    {"ticker": "GLN", "company_name": "Glencore plc", "isin": "JE00B4T3BW64", "sector": "Mining", "market_cap_category": "Large Cap"},
    {"ticker": "GRT", "company_name": "Growthpoint Properties Limited", "isin": "ZAE000179420", "sector": "Real Estate", "market_cap_category": "Large Cap"},
    {"ticker": "HAR", "company_name": "Harmony Gold Mining Company Limited", "isin": "ZAE000015228", "sector": "Mining", "market_cap_category": "Large Cap"},
    {"ticker": "IMP", "company_name": "Impala Platinum Holdings Limited", "isin": "ZAE000083648", "sector": "Mining", "market_cap_category": "Large Cap"},
    {"ticker": "INL", "company_name": "Investec Limited", "isin": "ZAE000081949", "sector": "Financial Services", "market_cap_category": "Large Cap"},
    {"ticker": "INP", "company_name": "Investec plc", "isin": "GB00B17BBQ50", "sector": "Financial Services", "market_cap_category": "Large Cap"},
    {"ticker": "KIO", "company_name": "Kumba Iron Ore Limited", "isin": "ZAE000085346", "sector": "Mining", "market_cap_category": "Large Cap"},
    {"ticker": "MNP", "company_name": "Mondi plc", "isin": "GB00B1CRLC47", "sector": "Industrials", "market_cap_category": "Large Cap"},
    {"ticker": "MRP", "company_name": "Mr Price Group Limited", "isin": "ZAE000200457", "sector": "Consumer Services", "market_cap_category": "Large Cap"},
    {"ticker": "MTN", "company_name": "MTN Group Limited", "isin": "ZAE000042164", "sector": "Telecommunications", "market_cap_category": "Large Cap"},
    {"ticker": "NED", "company_name": "Nedbank Group Limited", "isin": "ZAE000004875", "sector": "Financial Services", "market_cap_category": "Large Cap"},
    {"ticker": "NPN", "company_name": "Naspers Limited", "isin": "ZAE000015889", "sector": "Technology", "market_cap_category": "Large Cap"},
    {"ticker": "NRP", "company_name": "NEPI Rockcastle N.V.", "isin": "NL0015000RT2", "sector": "Real Estate", "market_cap_category": "Large Cap"},
    {"ticker": "OMU", "company_name": "Old Mutual Limited", "isin": "ZAE000255360", "sector": "Financial Services", "market_cap_category": "Large Cap"},
    {"ticker": "PRX", "company_name": "Prosus N.V.", "isin": "NL0013654783", "sector": "Technology", "market_cap_category": "Large Cap"},
    {"ticker": "REM", "company_name": "Remgro Limited", "isin": "ZAE000026480", "sector": "Industrials", "market_cap_category": "Large Cap"},
    {"ticker": "SBK", "company_name": "Standard Bank Group Limited", "isin": "ZAE000109815", "sector": "Financial Services", "market_cap_category": "Large Cap"},
    {"ticker": "SHP", "company_name": "Shoprite Holdings Limited", "isin": "ZAE000012084", "sector": "Consumer Services", "market_cap_category": "Large Cap"},
    {"ticker": "SLM", "company_name": "Sanlam Limited", "isin": "ZAE000070660", "sector": "Financial Services", "market_cap_category": "Large Cap"},
    {"ticker": "SOL", "company_name": "Sasol Limited", "isin": "ZAE000006896", "sector": "Chemicals", "market_cap_category": "Large Cap"},
    {"ticker": "SSW", "company_name": "Sibanye Stillwater Limited", "isin": "ZAE000259701", "sector": "Mining", "market_cap_category": "Large Cap"},
    {"ticker": "VOD", "company_name": "Vodacom Group Limited", "isin": "ZAE000132577", "sector": "Telecommunications", "market_cap_category": "Large Cap"},
    {"ticker": "WHL", "company_name": "Woolworths Holdings Limited", "isin": "ZAE000063863", "sector": "Consumer Services", "market_cap_category": "Large Cap"},
    # Mid Cap
    {"ticker": "ABG", "company_name": "Absa Group Limited", "isin": "ZAE000255915", "sector": "Financial Services", "market_cap_category": "Mid Cap"},
    {"ticker": "APN", "company_name": "Aspen Pharmacare Holdings Limited", "isin": "ZAE000066692", "sector": "Healthcare", "market_cap_category": "Mid Cap"},
    {"ticker": "ARI", "company_name": "African Rainbow Minerals Limited", "isin": "ZAE000054045", "sector": "Mining", "market_cap_category": "Mid Cap"},
    {"ticker": "CCO", "company_name": "Capital & Counties Properties plc", "isin": "GB00B62G9D36", "sector": "Real Estate", "market_cap_category": "Mid Cap"},
    {"ticker": "DCP", "company_name": "Dis-Chem Pharmacies Limited", "isin": "ZAE000227831", "sector": "Consumer Services", "market_cap_category": "Mid Cap"},
    {"ticker": "DGH", "company_name": "DataTec Limited", "isin": "ZAE000017745", "sector": "Technology", "market_cap_category": "Mid Cap"},
    {"ticker": "DRD", "company_name": "DRDGOLD Limited", "isin": "ZAE000058723", "sector": "Mining", "market_cap_category": "Mid Cap"},
    {"ticker": "EQU", "company_name": "Equites Property Fund Limited", "isin": "ZAE000188843", "sector": "Real Estate", "market_cap_category": "Mid Cap"},
    {"ticker": "FBR", "company_name": "Famous Brands Limited", "isin": "ZAE000053328", "sector": "Consumer Services", "market_cap_category": "Mid Cap"},
    {"ticker": "GND", "company_name": "Grindrod Limited", "isin": "ZAE000072328", "sector": "Industrials", "market_cap_category": "Mid Cap"},
    {"ticker": "HAM", "company_name": "Hammerson plc", "isin": "GB0004065016", "sector": "Real Estate", "market_cap_category": "Mid Cap"},
    {"ticker": "HMN", "company_name": "Hammerson plc", "isin": "GB0004065016", "sector": "Real Estate", "market_cap_category": "Mid Cap"},
    {"ticker": "IPL", "company_name": "Imperial Logistics Limited", "isin": "ZAE000067211", "sector": "Industrials", "market_cap_category": "Mid Cap"},
    {"ticker": "ITU", "company_name": "Italtile Limited", "isin": "ZAE000099123", "sector": "Industrials", "market_cap_category": "Mid Cap"},
    {"ticker": "JSE", "company_name": "JSE Limited", "isin": "ZAE000079711", "sector": "Financial Services", "market_cap_category": "Mid Cap"},
    {"ticker": "KAP", "company_name": "KAP Industrial Holdings Limited", "isin": "ZAE000171963", "sector": "Industrials", "market_cap_category": "Mid Cap"},
    {"ticker": "LBH", "company_name": "Liberty Holdings Limited", "isin": "ZAE000127148", "sector": "Financial Services", "market_cap_category": "Mid Cap"},
    {"ticker": "LEW", "company_name": "Lewis Group Limited", "isin": "ZAE000058236", "sector": "Consumer Services", "market_cap_category": "Mid Cap"},
    {"ticker": "LHC", "company_name": "Life Healthcare Group Holdings Limited", "isin": "ZAE000145892", "sector": "Healthcare", "market_cap_category": "Mid Cap"},
    {"ticker": "MCG", "company_name": "MultiChoice Group Limited", "isin": "ZAE000265971", "sector": "Consumer Services", "market_cap_category": "Mid Cap"},
    {"ticker": "MEI", "company_name": "Mediclinic International plc", "isin": "GB00B8HX8Z92", "sector": "Healthcare", "market_cap_category": "Mid Cap"},
    {"ticker": "MND", "company_name": "Mondi Limited", "isin": "ZAE000156550", "sector": "Industrials", "market_cap_category": "Mid Cap"},
    {"ticker": "MSM", "company_name": "Massmart Holdings Limited", "isin": "ZAE000152617", "sector": "Consumer Services", "market_cap_category": "Mid Cap"},
    {"ticker": "MSP", "company_name": "MAS Real Estate Inc", "isin": "VGG5765K1072", "sector": "Real Estate", "market_cap_category": "Mid Cap"},
    {"ticker": "MTH", "company_name": "Motus Holdings Limited", "isin": "ZAE000261913", "sector": "Consumer Services", "market_cap_category": "Mid Cap"},
    {"ticker": "MTM", "company_name": "Momentum Metropolitan Holdings Limited", "isin": "ZAE000269890", "sector": "Financial Services", "market_cap_category": "Mid Cap"},
    {"ticker": "NPH", "company_name": "Northam Platinum Holdings Limited", "isin": "ZAE000030912", "sector": "Mining", "market_cap_category": "Mid Cap"},
    {"ticker": "NTC", "company_name": "Netcare Limited", "isin": "ZAE000011953", "sector": "Healthcare", "market_cap_category": "Mid Cap"},
    {"ticker": "OMN", "company_name": "Omnia Holdings Limited", "isin": "ZAE000005153", "sector": "Chemicals", "market_cap_category": "Mid Cap"},
    {"ticker": "PAN", "company_name": "Pan African Resources plc", "isin": "GB0004300496", "sector": "Mining", "market_cap_category": "Mid Cap"},
    {"ticker": "PIK", "company_name": "Pick n Pay Stores Limited", "isin": "ZAE000005443", "sector": "Consumer Services", "market_cap_category": "Mid Cap"},
    {"ticker": "PPH", "company_name": "Pepkor Holdings Limited", "isin": "ZAE000259479", "sector": "Consumer Services", "market_cap_category": "Mid Cap"},
    {"ticker": "RBP", "company_name": "Royal Bafokeng Platinum Limited", "isin": "ZAE000149936", "sector": "Mining", "market_cap_category": "Mid Cap"},
    {"ticker": "RDF", "company_name": "Redefine Properties Limited", "isin": "ZAE000190252", "sector": "Real Estate", "market_cap_category": "Mid Cap"},
    {"ticker": "REN", "company_name": "Reunert Limited", "isin": "ZAE000057428", "sector": "Industrials", "market_cap_category": "Mid Cap"},
    {"ticker": "RES", "company_name": "Resilient REIT Limited", "isin": "ZAE000202331", "sector": "Real Estate", "market_cap_category": "Mid Cap"},
    {"ticker": "RLO", "company_name": "Reunion Gold Corporation", "isin": "ZAE000057507", "sector": "Mining", "market_cap_category": "Mid Cap"},
    {"ticker": "RNI", "company_name": "Reinet Investments S.C.A.", "isin": "LU0383812293", "sector": "Financial Services", "market_cap_category": "Mid Cap"},
    {"ticker": "SAP", "company_name": "Sappi Limited", "isin": "ZAE000006284", "sector": "Industrials", "market_cap_category": "Mid Cap"},
    {"ticker": "SRE", "company_name": "Sirius Real Estate Limited", "isin": "GG00B1W3VF54", "sector": "Real Estate", "market_cap_category": "Mid Cap"},
    {"ticker": "SPP", "company_name": "Spar Group Limited", "isin": "ZAE000058517", "sector": "Consumer Services", "market_cap_category": "Mid Cap"},
    {"ticker": "TBS", "company_name": "Tiger Brands Limited", "isin": "ZAE000071080", "sector": "Consumer Goods", "market_cap_category": "Mid Cap"},
    {"ticker": "TFG", "company_name": "The Foschini Group Limited", "isin": "ZAE000148466", "sector": "Consumer Services", "market_cap_category": "Mid Cap"},
    {"ticker": "TGA", "company_name": "Thungela Resources Limited", "isin": "GB00BN4RK096", "sector": "Mining", "market_cap_category": "Mid Cap"},
    {"ticker": "TKG", "company_name": "Telkom SA SOC Limited", "isin": "ZAE000044897", "sector": "Telecommunications", "market_cap_category": "Mid Cap"},
    {"ticker": "TRU", "company_name": "Truworths International Limited", "isin": "ZAE000028296", "sector": "Consumer Services", "market_cap_category": "Mid Cap"},
    {"ticker": "TSG", "company_name": "Tsogo Sun Gaming Limited", "isin": "ZAE000273116", "sector": "Consumer Services", "market_cap_category": "Mid Cap"},
    {"ticker": "WBO", "company_name": "Wilson Bayly Holmes-Ovcon Limited", "isin": "ZAE000009932", "sector": "Industrials", "market_cap_category": "Mid Cap"},
    # Small Cap
    {"ticker": "ACL", "company_name": "ArcelorMittal South Africa Limited", "isin": "ZAE000134961", "sector": "Mining", "market_cap_category": "Small Cap"},
    {"ticker": "ADH", "company_name": "ADvTECH Limited", "isin": "ZAE000031035", "sector": "Consumer Services", "market_cap_category": "Small Cap"},
    {"ticker": "ADR", "company_name": "Adcorp Holdings Limited", "isin": "ZAE000000139", "sector": "Industrials", "market_cap_category": "Small Cap"},
    {"ticker": "AFE", "company_name": "AECI Limited", "isin": "ZAE000000220", "sector": "Chemicals", "market_cap_category": "Small Cap"},
    {"ticker": "AFT", "company_name": "Afrimat Limited", "isin": "ZAE000086302", "sector": "Industrials", "market_cap_category": "Small Cap"},
    {"ticker": "AIL", "company_name": "African Infrastructure Investment Managers", "isin": "ZAE000314575", "sector": "Financial Services", "market_cap_category": "Small Cap"},
    {"ticker": "ALP", "company_name": "Alphamin Resources Corp", "isin": "VGG0380V1040", "sector": "Mining", "market_cap_category": "Small Cap"},
    {"ticker": "AVI", "company_name": "AVI Limited", "isin": "ZAE000049433", "sector": "Consumer Goods", "market_cap_category": "Small Cap"},
    {"ticker": "BAW", "company_name": "Barloworld Limited", "isin": "ZAE000026639", "sector": "Industrials", "market_cap_category": "Small Cap"},
    {"ticker": "BEL", "company_name": "Bell Equipment Limited", "isin": "ZAE000028304", "sector": "Industrials", "market_cap_category": "Small Cap"},
    {"ticker": "BRT", "company_name": "Bryte Insurance Company Limited", "isin": "ZAE000201805", "sector": "Financial Services", "market_cap_category": "Small Cap"},
    {"ticker": "CAT", "company_name": "Caxton and CTP Publishers and Printers Limited", "isin": "ZAE000043345", "sector": "Consumer Services", "market_cap_category": "Small Cap"},
    {"ticker": "CLH", "company_name": "City Lodge Hotels Limited", "isin": "ZAE000117792", "sector": "Consumer Services", "market_cap_category": "Small Cap"},
    {"ticker": "CMH", "company_name": "Combined Motor Holdings Limited", "isin": "ZAE000003182", "sector": "Consumer Services", "market_cap_category": "Small Cap"},
    {"ticker": "CML", "company_name": "Coronation Fund Managers Limited", "isin": "ZAE000047353", "sector": "Financial Services", "market_cap_category": "Small Cap"},
    {"ticker": "CSB", "company_name": "Cashbuild Limited", "isin": "ZAE000028320", "sector": "Consumer Services", "market_cap_category": "Small Cap"},
    {"ticker": "DIB", "company_name": "Distell Group Holdings Limited", "isin": "ZAE000028668", "sector": "Consumer Goods", "market_cap_category": "Small Cap"},
    {"ticker": "EMI", "company_name": "Emira Property Fund Limited", "isin": "ZAE000203204", "sector": "Real Estate", "market_cap_category": "Small Cap"},
    {"ticker": "EOH", "company_name": "EOH Holdings Limited", "isin": "ZAE000071072", "sector": "Technology", "market_cap_category": "Small Cap"},
    {"ticker": "EPP", "company_name": "EPP N.V.", "isin": "NL0012367", "sector": "Real Estate", "market_cap_category": "Small Cap"},
    {"ticker": "GRF", "company_name": "Group Five Limited", "isin": "ZAE000004610", "sector": "Industrials", "market_cap_category": "Small Cap"},
    {"ticker": "HCI", "company_name": "Hosken Consolidated Investments Limited", "isin": "ZAE000003257", "sector": "Financial Services", "market_cap_category": "Small Cap"},
    {"ticker": "HDC", "company_name": "Hudaco Industries Limited", "isin": "ZAE000003273", "sector": "Industrials", "market_cap_category": "Small Cap"},
    {"ticker": "HPB", "company_name": "Hospitality Property Fund Limited", "isin": "ZAE000203226", "sector": "Real Estate", "market_cap_category": "Small Cap"},
    {"ticker": "HYP", "company_name": "Hyprop Investments Limited", "isin": "ZAE000190724", "sector": "Real Estate", "market_cap_category": "Small Cap"},
    {"ticker": "ITE", "company_name": "Italtile Limited", "isin": "ZAE000099123", "sector": "Industrials", "market_cap_category": "Small Cap"},
    {"ticker": "KST", "company_name": "PSG Konsult Limited", "isin": "ZAE000191417", "sector": "Financial Services", "market_cap_category": "Small Cap"},
    {"ticker": "LON", "company_name": "Lonmin plc", "isin": "GB0031192486", "sector": "Mining", "market_cap_category": "Small Cap"},
    {"ticker": "MAS", "company_name": "MAS Real Estate Inc", "isin": "VGG5765K1072", "sector": "Real Estate", "market_cap_category": "Small Cap"},
    {"ticker": "MFB", "company_name": "M&F Smiths Holdings Limited", "isin": "ZAE000009924", "sector": "Consumer Goods", "market_cap_category": "Small Cap"},
    {"ticker": "MMP", "company_name": "Marshall Monteagle plc", "isin": "JE00B2QKY057", "sector": "Industrials", "market_cap_category": "Small Cap"},
    {"ticker": "MUR", "company_name": "Murray & Roberts Holdings Limited", "isin": "ZAE000073441", "sector": "Industrials", "market_cap_category": "Small Cap"},
    {"ticker": "NET", "company_name": "Net 1 UEPS Technologies Inc", "isin": "US64107N2062", "sector": "Technology", "market_cap_category": "Small Cap"},
    {"ticker": "NHM", "company_name": "Nampak Limited", "isin": "ZAE000071676", "sector": "Industrials", "market_cap_category": "Small Cap"},
    {"ticker": "OCE", "company_name": "Oceana Group Limited", "isin": "ZAE000025284", "sector": "Consumer Goods", "market_cap_category": "Small Cap"},
    {"ticker": "PPC", "company_name": "PPC Limited", "isin": "ZAE000170049", "sector": "Industrials", "market_cap_category": "Small Cap"},
    {"ticker": "PSG", "company_name": "PSG Financial Services Limited", "isin": "ZAE000013017", "sector": "Financial Services", "market_cap_category": "Small Cap"},
    {"ticker": "QUA", "company_name": "Quantum Foods Holdings Limited", "isin": "ZAE000193686", "sector": "Consumer Goods", "market_cap_category": "Small Cap"},
    {"ticker": "RBX", "company_name": "Raubex Group Limited", "isin": "ZAE000093183", "sector": "Industrials", "market_cap_category": "Small Cap"},
    {"ticker": "RFG", "company_name": "RFG Holdings Limited", "isin": "ZAE000191979", "sector": "Consumer Goods", "market_cap_category": "Small Cap"},
    {"ticker": "SNH", "company_name": "Steinhoff International Holdings N.V.", "isin": "NL0011375019", "sector": "Consumer Services", "market_cap_category": "Small Cap"},
    {"ticker": "SNT", "company_name": "Santam Limited", "isin": "ZAE000093779", "sector": "Financial Services", "market_cap_category": "Small Cap"},
    {"ticker": "SPG", "company_name": "Super Group Limited", "isin": "ZAE000161832", "sector": "Industrials", "market_cap_category": "Small Cap"},
    {"ticker": "SUI", "company_name": "Sun International Limited", "isin": "ZAE000097580", "sector": "Consumer Services", "market_cap_category": "Small Cap"},
    {"ticker": "THA", "company_name": "Tharisa plc", "isin": "CY0103562118", "sector": "Mining", "market_cap_category": "Small Cap"},
    {"ticker": "TON", "company_name": "Tongaat Hulett Limited", "isin": "ZAE000096541", "sector": "Consumer Goods", "market_cap_category": "Small Cap"},
    {"ticker": "TPC", "company_name": "Transpaco Limited", "isin": "ZAE000006466", "sector": "Industrials", "market_cap_category": "Small Cap"},
    {"ticker": "TXT", "company_name": "Textainer Group Holdings Limited", "isin": "BMG8766E1093", "sector": "Industrials", "market_cap_category": "Small Cap"},
    {"ticker": "WEZ", "company_name": "Wesizwe Platinum Limited", "isin": "ZAE000075859", "sector": "Mining", "market_cap_category": "Small Cap"},
    {"ticker": "YRK", "company_name": "York Timber Holdings Limited", "isin": "ZAE000133450", "sector": "Industrials", "market_cap_category": "Small Cap"},
    {"ticker": "ZED", "company_name": "Zeder Investments Limited", "isin": "ZAE000088431", "sector": "Financial Services", "market_cap_category": "Small Cap"},
]


class Command(BaseCommand):
    help = "Seed the JSECompany table with JSE-listed companies."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing JSE companies before seeding.",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            count = JSECompany.objects.count()
            JSECompany.objects.all().delete()
            self.stdout.write(f"Cleared {count} existing JSE companies.")

        created = 0
        updated = 0
        for entry in JSE_COMPANIES:
            _, was_created = JSECompany.objects.update_or_create(
                ticker=entry["ticker"],
                defaults={
                    "company_name": entry["company_name"],
                    "isin": entry.get("isin", ""),
                    "sector": entry.get("sector", ""),
                    "market_cap_category": entry.get("market_cap_category", ""),
                    "registration_number": entry.get("registration_number", ""),
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded JSE companies: {created} created, {updated} updated."
            )
        )
