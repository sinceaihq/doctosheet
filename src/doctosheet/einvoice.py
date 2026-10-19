"""Structured e-invoices: exact values, no OCR.

Supported syntaxes of the European standard EN 16931 and national formats:

* UN/CEFACT Cross Industry Invoice (CII) — Factur-X / ZUGFeRD (embedded in PDF/A-3)
  and XRechnung CII;
* OASIS UBL 2.1 Invoice and CreditNote — Peppol BIS Billing 3.0, XRechnung UBL;
* Finvoice 3.0 (Finland).

XML is parsed with defusedxml (no external entities, no entity expansion).
Elements are matched by local name, so namespace prefixes do not matter.
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal, InvalidOperation
from xml.etree.ElementTree import Element

from defusedxml.ElementTree import fromstring

from .model import Field, LineItem, VatRow

MAX_XML_BYTES = 5_000_000


class EInvoiceError(ValueError):
    pass


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find(el: Element | None, path: str) -> Element | None:
    """Child by a "/"-separated path of local names ("*" matches any)."""
    if el is None:
        return None
    current: list[Element] = [el]
    for part in path.split("/"):
        nxt = []
        for c in current:
            nxt.extend(ch for ch in c if part == "*" or _local(ch.tag) == part)
        if not nxt:
            return None
        current = nxt
    return current[0]


def _findall(el: Element | None, name: str) -> list[Element]:
    if el is None:
        return []
    return [x for x in el.iter() if _local(x.tag) == name]


def _first(*els: Element | None) -> Element | None:
    """First element that exists (Elements without children are falsy, so no ``or``)."""
    return next((e for e in els if e is not None), None)


def _text(el: Element | None, path: str | None = None) -> str | None:
    node = _find(el, path) if path else el
    if node is None or node.text is None:
        return None
    t = node.text.strip()
    return t or None


def _xml_field(value: str | None, what: str) -> Field:
    if value is None:
        return Field(None)
    return Field(value, value, "xml", None, "high", [f"e-invoice element {what}"])


def _amount(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return f"{Decimal(value):.2f}"
    except InvalidOperation:
        return None


def _number(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return f"{Decimal(value).normalize():f}"
    except InvalidOperation:
        return None


def _date(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(v[:10] if "-" in v else v[:8], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _vat_id(value: str | None) -> str | None:
    return re.sub(r"[\s.\-]", "", value).upper() if value else None


def _iban(value: str | None) -> str | None:
    return re.sub(r"\s", "", value).upper() if value else None


def parse(data: bytes) -> tuple[str, dict[str, Field], list[LineItem], list[VatRow]]:
    if len(data) > MAX_XML_BYTES:
        raise EInvoiceError("The XML file is too large.")
    try:
        root = fromstring(data)
    except Exception as exc:
        raise EInvoiceError(f"Not valid XML ({type(exc).__name__}).") from exc
    name = _local(root.tag)
    if name == "CrossIndustryInvoice":
        return ("CII (Factur-X / ZUGFeRD / XRechnung)", *_cii(root))
    if name in ("Invoice", "CreditNote"):
        return ("UBL (Peppol BIS / XRechnung)", *_ubl(root))
    if name == "Finvoice":
        return ("Finvoice", *_finvoice(root))
    raise EInvoiceError(f"Unsupported XML document type “{name}”.")


def _cii(root: Element) -> tuple[dict[str, Field], list[LineItem], list[VatRow]]:
    doc = _find(root, "ExchangedDocument")
    trade = _find(root, "SupplyChainTradeTransaction")
    agreement = _find(trade, "ApplicableHeaderTradeAgreement")
    settlement = _find(trade, "ApplicableHeaderTradeSettlement")
    seller = _find(agreement, "SellerTradeParty")
    buyer = _find(agreement, "BuyerTradeParty")
    summ = _find(settlement, "SpecifiedTradeSettlementHeaderMonetarySummation")

    def party_vat(party: Element | None) -> str | None:
        for reg in _findall(party, "SpecifiedTaxRegistration"):
            idn = _find(reg, "ID")
            if idn is not None and idn.get("schemeID") == "VA":
                return _text(idn)
        return None

    tax_total = None
    for el in _findall(summ, "TaxTotalAmount"):
        cur = el.get("currencyID")
        if cur is None or cur == _text(settlement, "InvoiceCurrencyCode"):
            tax_total = _text(el)
            break
    fields = {
        "invoice_number": _xml_field(_text(doc, "ID"), "ExchangedDocument/ID"),
        "issue_date": _xml_field(_date(_text(doc, "IssueDateTime/DateTimeString")), "IssueDateTime"),
        "due_date": _xml_field(
            _date(_text(settlement, "SpecifiedTradePaymentTerms/DueDateDateTime/DateTimeString")), "DueDateDateTime"
        ),
        "currency": _xml_field(_text(settlement, "InvoiceCurrencyCode"), "InvoiceCurrencyCode"),
        "seller_name": _xml_field(_text(seller, "Name"), "SellerTradeParty/Name"),
        "seller_vat_id": _xml_field(_vat_id(party_vat(seller)), "SellerTradeParty/SpecifiedTaxRegistration"),
        "buyer_name": _xml_field(_text(buyer, "Name"), "BuyerTradeParty/Name"),
        "buyer_vat_id": _xml_field(_vat_id(party_vat(buyer)), "BuyerTradeParty/SpecifiedTaxRegistration"),
        "iban": _xml_field(
            _iban(_text(settlement, "SpecifiedTradeSettlementPaymentMeans/PayeePartyCreditorFinancialAccount/IBANID")),
            "PayeePartyCreditorFinancialAccount/IBANID",
        ),
        "net_amount": _xml_field(_amount(_text(summ, "TaxBasisTotalAmount")), "TaxBasisTotalAmount"),
        "vat_amount": _xml_field(_amount(tax_total), "TaxTotalAmount"),
        "total_amount": _xml_field(_amount(_text(summ, "GrandTotalAmount")), "GrandTotalAmount"),
    }
    breakdown = [
        VatRow(
            _xml_field(_number(_text(t, "RateApplicablePercent")), "ApplicableTradeTax/RateApplicablePercent"),
            _xml_field(_amount(_text(t, "BasisAmount")), "ApplicableTradeTax/BasisAmount"),
            _xml_field(_amount(_text(t, "CalculatedAmount")), "ApplicableTradeTax/CalculatedAmount"),
        )
        for t in ([] if settlement is None else [x for x in settlement if _local(x.tag) == "ApplicableTradeTax"])
    ]
    items = []
    for li in _findall(trade, "IncludedSupplyChainTradeLineItem"):
        qty_el = _find(li, "SpecifiedLineTradeDelivery/BilledQuantity")
        items.append(
            LineItem(
                _xml_field(_text(li, "SpecifiedTradeProduct/Name"), "SpecifiedTradeProduct/Name"),
                _xml_field(_number(_text(qty_el)), "BilledQuantity"),
                _xml_field(qty_el.get("unitCode") if qty_el is not None else None, "BilledQuantity/@unitCode"),
                _xml_field(
                    _amount(_text(li, "SpecifiedLineTradeAgreement/NetPriceProductTradePrice/ChargeAmount")),
                    "NetPriceProductTradePrice",
                ),
                _xml_field(
                    _number(_text(li, "SpecifiedLineTradeSettlement/ApplicableTradeTax/RateApplicablePercent")),
                    "RateApplicablePercent",
                ),
                _xml_field(
                    _amount(
                        _text(li, "SpecifiedLineTradeSettlement/SpecifiedTradeSettlementLineMonetarySummation/LineTotalAmount")
                    ),
                    "LineTotalAmount",
                ),
            )
        )
    return fields, items, breakdown


def _ubl(root: Element) -> tuple[dict[str, Field], list[LineItem], list[VatRow]]:
    def party(kind: str) -> Element | None:
        return _find(root, f"{kind}/Party")

    def name(p: Element | None) -> str | None:
        return _text(p, "PartyLegalEntity/RegistrationName") or _text(p, "PartyName/Name")

    def vat(p: Element | None) -> str | None:
        for pts in _findall(p, "PartyTaxScheme"):
            if (_text(pts, "TaxScheme/ID") or "VAT").upper() == "VAT":
                return _text(pts, "CompanyID")
        return None

    totals = _find(root, "LegalMonetaryTotal")
    tax_totals = [x for x in root if _local(x.tag) == "TaxTotal"]
    currency = _text(root, "DocumentCurrencyCode")
    tax_amount = None
    for tt in tax_totals:
        el = _find(tt, "TaxAmount")
        if el is not None and (el.get("currencyID") in (None, currency)):
            tax_amount = _text(el)
            break
    seller, buyer = party("AccountingSupplierParty"), party("AccountingCustomerParty")
    due = _text(root, "DueDate") or _text(root, "PaymentMeans/PaymentDueDate")
    fields = {
        "invoice_number": _xml_field(_text(root, "ID"), "cbc:ID"),
        "issue_date": _xml_field(_date(_text(root, "IssueDate")), "cbc:IssueDate"),
        "due_date": _xml_field(_date(due), "cbc:DueDate"),
        "currency": _xml_field(currency, "cbc:DocumentCurrencyCode"),
        "seller_name": _xml_field(name(seller), "AccountingSupplierParty"),
        "seller_vat_id": _xml_field(_vat_id(vat(seller)), "AccountingSupplierParty/PartyTaxScheme"),
        "buyer_name": _xml_field(name(buyer), "AccountingCustomerParty"),
        "buyer_vat_id": _xml_field(_vat_id(vat(buyer)), "AccountingCustomerParty/PartyTaxScheme"),
        "iban": _xml_field(_iban(_text(root, "PaymentMeans/PayeeFinancialAccount/ID")), "PayeeFinancialAccount/ID"),
        "net_amount": _xml_field(_amount(_text(totals, "TaxExclusiveAmount")), "TaxExclusiveAmount"),
        "vat_amount": _xml_field(_amount(tax_amount), "TaxTotal/TaxAmount"),
        "total_amount": _xml_field(_amount(_text(totals, "TaxInclusiveAmount")), "TaxInclusiveAmount"),
    }
    breakdown = []
    for tt in tax_totals[:1]:
        for sub in [x for x in tt if _local(x.tag) == "TaxSubtotal"]:
            breakdown.append(
                VatRow(
                    _xml_field(_number(_text(sub, "TaxCategory/Percent")), "TaxCategory/Percent"),
                    _xml_field(_amount(_text(sub, "TaxableAmount")), "TaxableAmount"),
                    _xml_field(_amount(_text(sub, "TaxAmount")), "TaxAmount"),
                )
            )
    items = []
    for line in [x for x in root if _local(x.tag) in ("InvoiceLine", "CreditNoteLine")]:
        qty_el = _first(_find(line, "InvoicedQuantity"), _find(line, "CreditedQuantity"))
        items.append(
            LineItem(
                _xml_field(_text(line, "Item/Name") or _text(line, "Item/Description"), "Item/Name"),
                _xml_field(_number(_text(qty_el)), "InvoicedQuantity"),
                _xml_field(qty_el.get("unitCode") if qty_el is not None else None, "InvoicedQuantity/@unitCode"),
                _xml_field(_amount(_text(line, "Price/PriceAmount")), "Price/PriceAmount"),
                _xml_field(_number(_text(line, "Item/ClassifiedTaxCategory/Percent")), "ClassifiedTaxCategory/Percent"),
                _xml_field(_amount(_text(line, "LineExtensionAmount")), "LineExtensionAmount"),
            )
        )
    return fields, items, breakdown


def _finvoice(root: Element) -> tuple[dict[str, Field], list[LineItem], list[VatRow]]:
    details = _find(root, "InvoiceDetails")
    seller = _find(root, "SellerPartyDetails")
    buyer = _find(root, "BuyerPartyDetails")
    total_excl = _find(details, "InvoiceTotalVatExcludedAmount")
    fields = {
        "invoice_number": _xml_field(_text(details, "InvoiceNumber"), "InvoiceNumber"),
        "issue_date": _xml_field(_date(_text(details, "InvoiceDate")), "InvoiceDate"),
        "due_date": _xml_field(_date(_text(details, "PaymentTermsDetails/InvoiceDueDate")), "InvoiceDueDate"),
        "currency": _xml_field(total_excl.get("AmountCurrencyIdentifier") if total_excl is not None else None,
                               "AmountCurrencyIdentifier"),  # fmt: skip
        "seller_name": _xml_field(_text(seller, "SellerOrganisationName"), "SellerOrganisationName"),
        "seller_vat_id": _xml_field(_vat_id(_text(seller, "SellerOrganisationTaxCode")), "SellerOrganisationTaxCode"),
        "buyer_name": _xml_field(_text(buyer, "BuyerOrganisationName"), "BuyerOrganisationName"),
        "buyer_vat_id": _xml_field(_vat_id(_text(buyer, "BuyerOrganisationTaxCode")), "BuyerOrganisationTaxCode"),
        "iban": _xml_field(_iban(_text(root, "SellerInformationDetails/SellerAccountDetails/SellerAccountID")),
                           "SellerAccountID"),  # fmt: skip
        "net_amount": _xml_field(_amount(_text(total_excl)), "InvoiceTotalVatExcludedAmount"),
        "vat_amount": _xml_field(_amount(_text(details, "InvoiceTotalVatAmount")), "InvoiceTotalVatAmount"),
        "total_amount": _xml_field(_amount(_text(details, "InvoiceTotalVatIncludedAmount")), "InvoiceTotalVatIncludedAmount"),
    }
    breakdown = [
        VatRow(
            _xml_field(_number(_text(v, "VatRatePercent")), "VatRatePercent"),
            _xml_field(_amount(_text(v, "VatBaseAmount")), "VatBaseAmount"),
            _xml_field(_amount(_text(v, "VatRateAmount")), "VatRateAmount"),
        )
        for v in _findall(details, "VatSpecificationDetails")
    ]
    items = []
    for row in _findall(root, "InvoiceRow"):
        qty_el = _first(_find(row, "DeliveredQuantity"), _find(row, "InvoicedQuantity"), _find(row, "OrderedQuantity"))
        items.append(
            LineItem(
                _xml_field(_text(row, "ArticleName"), "ArticleName"),
                _xml_field(_number(_text(qty_el)), "DeliveredQuantity"),
                _xml_field(qty_el.get("QuantityUnitCode") if qty_el is not None else None, "QuantityUnitCode"),
                _xml_field(_amount(_text(row, "UnitPriceAmount")), "UnitPriceAmount"),
                _xml_field(_number(_text(row, "RowVatRatePercent")), "RowVatRatePercent"),
                _xml_field(_amount(_text(row, "RowVatExcludedAmount")), "RowVatExcludedAmount"),
            )
        )
    return fields, items, breakdown

