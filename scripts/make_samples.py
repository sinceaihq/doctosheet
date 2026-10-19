"""Generate the synthetic sample documents in tests/samples/ (used by tests and the demo).

    python scripts/make_samples.py

Companies are fictional. IBANs are the banks' published example accounts;
VAT numbers deliberately fail their check digits so that no real company's
number appears (DocToSheet flags them, which is part of the demonstration).
"""

from __future__ import annotations

import io
from decimal import Decimal
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parents[1] / "tests" / "samples"


def eu(v: Decimal) -> str:
    s = f"{v:,.2f}"
    return s.replace(",", " ").replace(".", ",")


def de(v: Decimal) -> str:
    s = f"{v:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fi_invoice() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, invariant=1)
    c.setTitle("Lasku 2026-1047")
    _w, h = A4
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, h - 60, "Pohjoistuuli Design Oy")
    c.setFont("Helvetica", 10)
    for i, t in enumerate(["Rantakatu 12 B", "90100 Oulu", "ALV-numero: FI12345672"]):
        c.drawString(50, h - 80 - i * 13, t)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(380, h - 60, "LASKU")
    c.setFont("Helvetica", 10)
    meta = [("Laskun numero", "2026-1047"), ("Päivämäärä", "15.3.2026"), ("Eräpäivä", "14.4.2026"),
            ("Viitenumero", "10473")]  # fmt: skip
    for i, (k, v) in enumerate(meta):
        c.drawString(380, h - 85 - i * 14, k)
        c.drawRightString(545, h - 85 - i * 14, v)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, h - 170, "Asiakas")
    c.setFont("Helvetica", 10)
    for i, t in enumerate(["Kaamos Kahvila Ky", "Torikatu 3", "96100 Rovaniemi"]):
        c.drawString(50, h - 185 - i * 13, t)
    y = h - 260
    c.setFont("Helvetica-Bold", 10)
    for x, t in [(50, "Kuvaus"), (300, "Määrä"), (360, "à-hinta"), (440, "ALV %"), (545, "Yhteensä")]:
        (c.drawRightString if x == 545 else c.drawString)(x, y, t)
    c.line(50, y - 5, 545, y - 5)
    c.setFont("Helvetica", 10)
    items = [("Logon suunnittelu", 1, Decimal("650.00")), ("Käyntikortit, 500 kpl", 2, Decimal("120.00")),
             ("Verkkosivujen päivitys (h)", 4, Decimal("90.00"))]  # fmt: skip
    net = Decimal(0)
    for i, (d, q, p) in enumerate(items):
        yy = y - 22 - i * 18
        amount = q * p
        net += amount
        c.drawString(50, yy, d)
        c.drawRightString(325, yy, str(q))
        c.drawRightString(410, yy, eu(p))
        c.drawRightString(470, yy, "25,5 %")
        c.drawRightString(545, yy, eu(amount))
    vat = (net * Decimal("0.255")).quantize(Decimal("0.01"))
    total = net + vat
    yy = y - 22 - len(items) * 18 - 20
    for k, v, bold in [
        ("Veroton yhteensä", net, False),
        ("ALV 25,5 %", vat, False),
        ("Maksettava yhteensä", total, True),
    ]:
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 10)
        c.drawString(360, yy, k)
        c.drawRightString(545, yy, f"{eu(v)} €")
        yy -= 16
    c.setFont("Helvetica", 9)
    c.drawString(
        50,
        60,
        "Pohjoistuuli Design Oy · Rantakatu 12 B, 90100 Oulu · IBAN: FI21 1234 5600 0007 85 · BIC: NDEAFIHH",
    )
    c.showPage()
    c.save()
    return buf.getvalue()


def de_items() -> list[tuple[str, int, Decimal, Decimal]]:
    return [("Wartung Heizungsanlage", 1, Decimal("480.00"), Decimal("19")),
            ("Ersatzteil Pumpe", 2, Decimal("135.50"), Decimal("19")),
            ("Fachbuch Heizungstechnik", 1, Decimal("49.90"), Decimal("7"))]  # fmt: skip


def de_invoice_pdf() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, invariant=1)
    _w, h = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, h - 60, "Bergwerk Haustechnik GmbH")
    c.setFont("Helvetica", 10)
    for i, t in enumerate(["Lindenallee 7", "80331 München", "USt-IdNr.: DE123456780"]):
        c.drawString(50, h - 80 - i * 13, t)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(380, h - 60, "RECHNUNG")
    c.setFont("Helvetica", 10)
    for i, (k, v) in enumerate([("Rechnungsnummer", "RE-2026-0311"), ("Rechnungsdatum", "02.03.2026"),
                                ("Zahlbar bis", "16.03.2026")]):  # fmt: skip
        c.drawString(380, h - 85 - i * 14, k)
        c.drawRightString(545, h - 85 - i * 14, v)
    c.drawString(50, h - 170, "Rechnungsempfänger")
    for i, t in enumerate(["Gasthaus Seeblick KG", "Uferweg 2", "82319 Starnberg"]):
        c.drawString(50, h - 185 - i * 13, t)
    y = h - 260
    c.setFont("Helvetica-Bold", 10)
    for x, t in [(50, "Bezeichnung"), (300, "Menge"), (360, "Einzelpreis"), (440, "USt."), (545, "Betrag")]:
        (c.drawRightString if x == 545 else c.drawString)(x, y, t)
    c.setFont("Helvetica", 10)
    net = Decimal(0)
    vat_by_rate: dict[Decimal, Decimal] = {}
    for i, (d, q, p, r) in enumerate(de_items()):
        yy = y - 22 - i * 18
        amount = q * p
        net += amount
        vat_by_rate[r] = vat_by_rate.get(r, Decimal(0)) + amount
        c.drawString(50, yy, d)
        c.drawRightString(325, yy, str(q))
        c.drawRightString(410, yy, de(p))
        c.drawRightString(470, yy, f"{r} %")
        c.drawRightString(545, yy, de(amount))
    yy = y - 22 - 3 * 18 - 20
    vat_total = Decimal(0)
    rows = [("Nettobetrag", net)]
    for r, base in vat_by_rate.items():
        v = (base * r / 100).quantize(Decimal("0.01"))
        vat_total += v
        rows.append((f"USt. {r} %", v))
    rows.append(("Rechnungsbetrag", net + vat_total))
    for k, v in rows:
        c.drawString(360, yy, k)
        c.drawRightString(545, yy, f"{de(v)} €")
        yy -= 16
    c.setFont("Helvetica", 9)
    c.drawString(50, 60, "Bankverbindung: IBAN DE89 3704 0044 0532 0130 00 · BIC COBADEFFXXX")
    c.showPage()
    c.save()
    return buf.getvalue()


def de_cii_xml() -> bytes:
    net = sum((q * p for _, q, p, _ in de_items()), Decimal(0))
    rates: dict[Decimal, Decimal] = {}
    for _, q, p, r in de_items():
        rates[r] = rates.get(r, Decimal(0)) + q * p
    taxes = {r: (b * r / 100).quantize(Decimal("0.01")) for r, b in rates.items()}
    vat = sum(taxes.values(), Decimal(0))
    lines = "".join(
        f"""<ram:IncludedSupplyChainTradeLineItem><ram:AssociatedDocumentLineDocument><ram:LineID>{i + 1}</ram:LineID></ram:AssociatedDocumentLineDocument>
<ram:SpecifiedTradeProduct><ram:Name>{d}</ram:Name></ram:SpecifiedTradeProduct>
<ram:SpecifiedLineTradeAgreement><ram:NetPriceProductTradePrice><ram:ChargeAmount>{p}</ram:ChargeAmount></ram:NetPriceProductTradePrice></ram:SpecifiedLineTradeAgreement>
<ram:SpecifiedLineTradeDelivery><ram:BilledQuantity unitCode="C62">{q}</ram:BilledQuantity></ram:SpecifiedLineTradeDelivery>
<ram:SpecifiedLineTradeSettlement><ram:ApplicableTradeTax><ram:TypeCode>VAT</ram:TypeCode><ram:CategoryCode>S</ram:CategoryCode><ram:RateApplicablePercent>{r}</ram:RateApplicablePercent></ram:ApplicableTradeTax>
<ram:SpecifiedTradeSettlementLineMonetarySummation><ram:LineTotalAmount>{q * p:.2f}</ram:LineTotalAmount></ram:SpecifiedTradeSettlementLineMonetarySummation></ram:SpecifiedLineTradeSettlement></ram:IncludedSupplyChainTradeLineItem>"""
        for i, (d, q, p, r) in enumerate(de_items())
    )
    tax_xml = "".join(
        f"""<ram:ApplicableTradeTax><ram:CalculatedAmount>{taxes[r]:.2f}</ram:CalculatedAmount><ram:TypeCode>VAT</ram:TypeCode><ram:BasisAmount>{b:.2f}</ram:BasisAmount><ram:CategoryCode>S</ram:CategoryCode><ram:RateApplicablePercent>{r}</ram:RateApplicablePercent></ram:ApplicableTradeTax>"""
        for r, b in rates.items()
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100" xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100" xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
<rsm:ExchangedDocumentContext><ram:GuidelineSpecifiedDocumentContextParameter><ram:ID>urn:cen.eu:en16931:2017</ram:ID></ram:GuidelineSpecifiedDocumentContextParameter></rsm:ExchangedDocumentContext>
<rsm:ExchangedDocument><ram:ID>RE-2026-0311</ram:ID><ram:TypeCode>380</ram:TypeCode><ram:IssueDateTime><udt:DateTimeString format="102">20260302</udt:DateTimeString></ram:IssueDateTime></rsm:ExchangedDocument>
<rsm:SupplyChainTradeTransaction>{lines}
<ram:ApplicableHeaderTradeAgreement>
<ram:SellerTradeParty><ram:Name>Bergwerk Haustechnik GmbH</ram:Name><ram:PostalTradeAddress><ram:CountryID>DE</ram:CountryID></ram:PostalTradeAddress><ram:SpecifiedTaxRegistration><ram:ID schemeID="VA">DE123456780</ram:ID></ram:SpecifiedTaxRegistration></ram:SellerTradeParty>
<ram:BuyerTradeParty><ram:Name>Gasthaus Seeblick KG</ram:Name><ram:PostalTradeAddress><ram:CountryID>DE</ram:CountryID></ram:PostalTradeAddress></ram:BuyerTradeParty>
</ram:ApplicableHeaderTradeAgreement>
<ram:ApplicableHeaderTradeDelivery/>
<ram:ApplicableHeaderTradeSettlement><ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
<ram:SpecifiedTradeSettlementPaymentMeans><ram:TypeCode>58</ram:TypeCode><ram:PayeePartyCreditorFinancialAccount><ram:IBANID>DE89370400440532013000</ram:IBANID></ram:PayeePartyCreditorFinancialAccount></ram:SpecifiedTradeSettlementPaymentMeans>
{tax_xml}
<ram:SpecifiedTradePaymentTerms><ram:DueDateDateTime><udt:DateTimeString format="102">20260316</udt:DateTimeString></ram:DueDateDateTime></ram:SpecifiedTradePaymentTerms>
<ram:SpecifiedTradeSettlementHeaderMonetarySummation><ram:LineTotalAmount>{net:.2f}</ram:LineTotalAmount><ram:TaxBasisTotalAmount>{net:.2f}</ram:TaxBasisTotalAmount><ram:TaxTotalAmount currencyID="EUR">{vat:.2f}</ram:TaxTotalAmount><ram:GrandTotalAmount>{net + vat:.2f}</ram:GrandTotalAmount><ram:DuePayableAmount>{net + vat:.2f}</ram:DuePayableAmount></ram:SpecifiedTradeSettlementHeaderMonetarySummation>
</ram:ApplicableHeaderTradeSettlement></rsm:SupplyChainTradeTransaction></rsm:CrossIndustryInvoice>""".encode()


def ubl_xml() -> bytes:
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
<cbc:CustomizationID>urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0</cbc:CustomizationID>
<cbc:ID>NL-2026-552</cbc:ID><cbc:IssueDate>2026-02-20</cbc:IssueDate><cbc:DueDate>2026-03-22</cbc:DueDate>
<cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode><cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
<cac:AccountingSupplierParty><cac:Party><cac:PartyTaxScheme><cbc:CompanyID>NL000099998B57</cbc:CompanyID><cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:PartyTaxScheme><cac:PartyLegalEntity><cbc:RegistrationName>Molenaar Vertalingen B.V.</cbc:RegistrationName></cac:PartyLegalEntity></cac:Party></cac:AccountingSupplierParty>
<cac:AccountingCustomerParty><cac:Party><cac:PartyLegalEntity><cbc:RegistrationName>Tulpenveld Logistiek B.V.</cbc:RegistrationName></cac:PartyLegalEntity></cac:Party></cac:AccountingCustomerParty>
<cac:PaymentMeans><cbc:PaymentMeansCode>58</cbc:PaymentMeansCode><cac:PayeeFinancialAccount><cbc:ID>NL91ABNA0417164300</cbc:ID></cac:PayeeFinancialAccount></cac:PaymentMeans>
<cac:TaxTotal><cbc:TaxAmount currencyID="EUR">252.00</cbc:TaxAmount><cac:TaxSubtotal><cbc:TaxableAmount currencyID="EUR">1200.00</cbc:TaxableAmount><cbc:TaxAmount currencyID="EUR">252.00</cbc:TaxAmount><cac:TaxCategory><cbc:ID>S</cbc:ID><cbc:Percent>21</cbc:Percent><cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:TaxCategory></cac:TaxSubtotal></cac:TaxTotal>
<cac:LegalMonetaryTotal><cbc:LineExtensionAmount currencyID="EUR">1200.00</cbc:LineExtensionAmount><cbc:TaxExclusiveAmount currencyID="EUR">1200.00</cbc:TaxExclusiveAmount><cbc:TaxInclusiveAmount currencyID="EUR">1452.00</cbc:TaxInclusiveAmount><cbc:PayableAmount currencyID="EUR">1452.00</cbc:PayableAmount></cac:LegalMonetaryTotal>
<cac:InvoiceLine><cbc:ID>1</cbc:ID><cbc:InvoicedQuantity unitCode="HUR">8</cbc:InvoicedQuantity><cbc:LineExtensionAmount currencyID="EUR">1200.00</cbc:LineExtensionAmount><cac:Item><cbc:Name>Vertaling handleiding (uren)</cbc:Name><cac:ClassifiedTaxCategory><cbc:ID>S</cbc:ID><cbc:Percent>21</cbc:Percent><cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:ClassifiedTaxCategory></cac:Item><cac:Price><cbc:PriceAmount currencyID="EUR">150.00</cbc:PriceAmount></cac:Price></cac:InvoiceLine>
</Invoice>"""


def receipt_png() -> bytes:
    """A receipt rendered to an image (OCR path)."""
    import pypdfium2 as pdfium

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(226, 400), invariant=1)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(113, 370, "Kahvila Kaamos Ky")
    c.setFont("Helvetica", 8)
    c.drawCentredString(113, 357, "Torikatu 3, 96100 Rovaniemi")
    c.drawString(14, 330, "Kuitin numero: 88123")
    c.drawString(14, 318, "Päivämäärä: 12.3.2026")
    y = 290
    for q, d, p in [
        (2, "Cappuccino", Decimal("4.20")),
        (1, "Korvapuusti", Decimal("3.50")),
        (3, "Vesi 0,5 l", Decimal("2.00")),
    ]:
        c.drawString(14, y, f"{q} x {d} à {eu(p)}")
        c.drawRightString(212, y, eu(q * p))
        y -= 14
    c.drawString(14, y - 10, "Yhteensä")
    c.drawRightString(212, y - 10, "17,90 €")
    c.drawString(14, y - 24, "ALV 14 %")
    c.drawRightString(212, y - 24, "2,20 €")
    c.showPage()
    c.save()
    page = pdfium.PdfDocument(buf.getvalue())[0]
    img = page.render(scale=3).to_pil().convert("L")
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def main() -> None:
    from facturx import generate_from_binary

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "invoice-fi.pdf").write_bytes(fi_invoice())
    (OUT / "invoice-de-zugferd.pdf").write_bytes(
        generate_from_binary(
            de_invoice_pdf(), de_cii_xml(), flavor="factur-x", level="en16931", check_xsd=False
        )
    )
    (OUT / "invoice-nl-peppol.xml").write_bytes(ubl_xml())
    (OUT / "receipt-fi.png").write_bytes(receipt_png())
    for f in sorted(OUT.iterdir()):
        print(f.name, f.stat().st_size)


if __name__ == "__main__":
    main()
