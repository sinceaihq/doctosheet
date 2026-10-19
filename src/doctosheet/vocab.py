"""Invoice vocabulary in European languages.

Written from general invoice practice (and the EN 16931 business terms), not
from any benchmark template. Matching is case-insensitive and accent-tolerant
(see ``norm``); phrases are matched on word boundaries.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache


def norm(text: str) -> str:
    """Case-folded, without diacritics, separators as spaces."""
    t = unicodedata.normalize("NFKD", text.casefold())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return (
        re.sub(r"[_\-–]+", " ", t).replace("ł", "l").replace("ø", "o").replace("æ", "ae").replace("ß", "ss")
    )


INVOICE_NUMBER: tuple[str, ...] = (
    "invoice no", "invoice number", "invoice nr", "invoice #", "invoice id", "inv no", "bill no", "receipt no",
    "laskun numero", "laskunumero", "laskun nro", "laskunro", "lasku nro", "kuitin numero",
    "fakturanummer", "fakturanr", "faktura nr", "fakturanummer", "kvittonummer",
    "rechnungsnummer", "rechnungsnr", "rechnung nr", "rechnungs nr", "belegnummer", "beleg nr",
    "numero de facture", "n de facture", "no de facture", "facture n", "facture no",
    "factuurnummer", "factuurnr", "factuur nr",
    "numero fattura", "fattura n", "n fattura", "fattura nr", "numero documento",
    "numero de factura", "factura n", "factura no", "n factura", "num factura",
    "numer faktury", "nr faktury", "faktura nr", "faktura vat nr",
    "numero da fatura", "fatura n", "fatura no",
    "cislo faktury", "faktura c", "cislo dokladu", "variabilni symbol",
    "fakturanummer", "faktura nr", "fakturanr",
    "szamla sorszama", "szamlaszam", "numar factura", "nr factura", "arve number", "arve nr",
    "saskaitos numeris", "rekina numurs", "racun st", "broj racuna", "cislo faktury",
)  # fmt: skip
_NUMBER_WORDS = ("nr", "no", "n", "nro", "num", "nummer", "number", "numero", "#", "c", "cislo")
_TITLES_FOR_NUMBER = ("invoice", "tax invoice", "credit note", "receipt", "rechnung", "handelsrechnung", "gutschrift",
                      "lasku", "faktura", "facture", "factuur", "fattura", "factura", "fatura", "kvitto", "quittung")  # fmt: skip
INVOICE_NUMBER = INVOICE_NUMBER + tuple(f"{t} {n}" for t in _TITLES_FOR_NUMBER for n in _NUMBER_WORDS)
# Issue date written after the invoice number: "Rechnung Nr. 471102 vom 05.03.2018".
ISSUED_ON = (
    "vom",
    "du",
    "del",
    "dated",
    "issued at",
    "issued on",
    "issued",
    "from",
    "date",
    "of",
    "den",
    "dne",
    "z dnia",
)

ISSUE_DATE = (
    "invoice date", "date of issue", "issue date", "issued", "date", "billing date", "receipt date",
    "laskun paivamaara", "laskun pvm", "paivays", "paivamaara", "pvm",
    "fakturadatum", "datum", "utfardad", "rechnungsdatum", "ausstellungsdatum", "belegdatum",
    "date de facture", "date d emission", "date de facturation", "factuurdatum", "datum factuur",
    "data fattura", "data di emissione", "data documento", "data", "fecha de factura", "fecha de emision",
    "fecha", "data wystawienia", "data faktury", "data da fatura", "data de emissao",
    "datum vystaveni", "vystaveno", "datum vyhotoveni", "fakturadato", "dato", "udstedt",
    "kelte", "szamla kelte", "data emiterii", "kuupaev", "arve kuupaev",
)  # fmt: skip
DUE_DATE = (
    "due date", "payment due", "due", "pay by", "payable by", "payment date",
    "erapaiva", "eraantyy", "maksettava viimeistaan", "forfallodatum", "forfaller", "forfallodag",
    "betalas senast", "falligkeitsdatum", "fallig am", "fallig", "zahlbar bis", "zahlungsziel",
    "date d echeance", "echeance", "a payer avant", "date limite de paiement", "vervaldatum",
    "te betalen voor", "uiterste betaaldatum", "data di scadenza", "scadenza", "fecha de vencimiento",
    "vencimiento", "fecha limite de pago", "termin platnosci", "termin zaplaty", "zaplata do",
    "data de vencimento", "vencimento", "pagar ate", "datum splatnosti", "splatnost", "splatne do",
    "forfaldsdato", "forfald", "betalingsfrist", "betales senest", "fizetesi hatarido",
    "data scadentei", "maksetahtaeg", "tahtaeg", "falligkeit", "fallig bis", "netto bis", "zahlbar innerhalb",
    "remit until", "pay until", "payable until", "please pay by", "please remit", "payment due by", "due by",
    "a regler avant", "payable avant", "te voldoen voor", "betalen voor", "pagare entro", "pagar antes de",
)  # fmt: skip
NET = (
    "subtotal", "sub total", "net amount", "net total", "total net", "total excl", "total excluding vat",
    "amount excl", "excl vat", "excl tax", "total before tax", "taxable amount",
    "veroton", "veroton yhteensa", "yhteensa veroton", "arvonlisaveroton", "summa exkl",
    "netto", "nettobelopp", "summa exkl moms", "nettobetrag", "zwischensumme", "summe netto",
    "gesamt netto", "total ht", "montant ht", "montant hors taxes", "sous total", "total hors taxes",
    "subtotaal", "totaal excl", "bedrag excl", "imponibile", "totale imponibile", "base imponible",
    "subtotal sin iva", "razem netto", "wartosc netto", "suma netto", "netto razem",
    "total sem iva", "valor liquido", "base tributavel", "zaklad dane", "celkem bez dph",
    "beløb ekskl", "belob ekskl", "ekskl moms", "netto belob", "nettobelop", "sum eks mva",
    "netto osszeg", "valoare fara tva", "summa kaibemaksuta", "ohne ust", "ohne mwst", "rechnungssumme ohne",
    "summe ohne", "positionssumme", "warenwert", "total before vat", "total without vat", "amount before tax",
    "net total", "total net amount",
)  # fmt: skip
VAT = (
    "vat", "value added tax", "tax", "sales tax", "alv", "arvonlisavero", "moms", "mervardesskatt",
    "mwst", "ust", "umsatzsteuer", "mehrwertsteuer", "tva", "btw", "iva", "imposta",
    "dph", "podatek vat", "kwota vat", "vat kwota", "mva", "afa", "kaibemaks", "pvm", "pvn", "ddv", "pdv",
    "steuerbetrag", "umsatzsteuerbetrag", "mwst betrag", "ust betrag", "vat amount", "tax amount", "montant tva",
)  # fmt: skip
# "VAT total", "Summe USt": a VAT line, unless it says the amount includes VAT.
INCLUDING = ("incl", "including", "inkl", "inklusive", "inc vat", "with vat", "ttc", "brutto", "gross", "sis alv",
             "sisaltaen alv", "inkl moms", "med moms", "med mva", "incl btw", "met btw", "mit mwst", "mit ust",
             "com iva", "con iva", "iva incluida", "iva inclusa", "avec tva", "z vat", "s dph", "vcetne dph")  # fmt: skip
TOTAL = (
    "amount due", "total due", "balance due", "grand total", "total amount", "invoice total", "total",
    "to pay", "amount payable", "total incl", "total including vat",
    "maksettava", "maksettava yhteensa", "yhteensa", "loppusumma", "att betala", "totalt", "summa att betala",
    "gesamtbetrag", "rechnungsbetrag", "endbetrag", "zu zahlen", "zahlbetrag", "gesamtsumme",
    "total ttc", "net a payer", "montant ttc", "montant total", "totaal", "totaal incl", "te betalen",
    "totaalbedrag", "totale", "totale fattura", "totale da pagare", "importo totale",
    "total factura", "total a pagar", "importe total", "do zaplaty", "razem brutto", "wartosc brutto",
    "suma brutto", "total com iva", "valor total", "total a pagar", "celkem k uhrade", "k uhrade",
    "celkem", "i alt", "i alt at betale", "at betale", "a betale", "totalt a betale",
    "fizetendo", "osszesen", "total de plata", "kokku", "tasuda", "bruttosumme", "bruttobetrag", "brutto",
    "due payable", "payable", "total payable", "amount to pay", "zu zahlender betrag", "gesamtsumme brutto",
)  # fmt: skip
SELLER = (
    "seller", "supplier", "vendor", "from", "billed by", "issued by", "payee",
    "myyja", "laskuttaja", "toimittaja", "saaja", "saljare", "leverantor", "avsandare",
    "verkaufer", "lieferant", "rechnungssteller", "vendeur", "fournisseur", "emetteur",
    "verkoper", "leverancier", "venditore", "fornitore", "cedente", "vendedor", "proveedor", "emisor",
    "sprzedawca", "dostawca", "fornecedor", "dodavatel", "prodavajici", "saelger", "leverandor",
)  # fmt: skip
BUYER = (
    "bill to", "billed to", "invoice to", "sold to", "customer", "client", "buyer", "recipient",
    "ostaja", "asiakas", "tilaaja", "laskutusosoite", "kopare", "kund", "fakturaadress",
    "kunde", "rechnungsempfanger", "rechnungsadresse", "auftraggeber", "facture a", "client",
    "destinataire", "adresse de facturation", "klant", "factuuradres", "afnemer",
    "cliente", "cessionario", "committente", "destinatario", "facturar a", "comprador",
    "nabywca", "odbiorca", "platnik", "adquirente", "odberatel", "kupujici", "kaufer", "leistungsempfanger",
    "invoice address", "billing address", "ship to", "bill to address",
    "kunde", "faktureres til", "modtager", "vevo", "cumparator",
)  # fmt: skip
IBAN = ("iban", "account", "bank account", "tilinumero", "tili", "konto", "kontonummer", "bankverbindung",
        "compte", "rib", "rekening", "rekeningnummer", "conto", "cuenta", "numer konta", "conta", "nib",
        "cislo uctu", "ucet", "kontonr", "bankkonto")  # fmt: skip
VAT_ID = (
    "vat no", "vat number", "vat reg", "vat id", "tax id", "vat", "alv numero", "alv tunniste", "y tunnus",
    "momsreg", "momsregistreringsnummer", "vat nr", "ust idnr", "ust id", "umsatzsteuer id", "steuernummer",
    "n tva", "tva intracommunautaire", "numero de tva", "btw nummer", "btw nr", "btw", "partita iva", "p iva",
    "nif", "cif", "nip", "nif iva", "dic", "cvr", "cvr nr", "mva", "org nr", "vat reg no", "tva", "n tva",
    "iva", "moms", "alv", "btw id", "ust idnr", "vat reg", "vat registration", "nip ue", "dic dph", "ic dph",
)  # fmt: skip
TITLE = ("invoice", "tax invoice", "receipt", "lasku", "kuitti", "faktura", "kvitto", "rechnung", "quittung",
         "facture", "factuur", "fattura", "factura", "fatura", "faktura vat", "danovy doklad", "kvittering",
         "szamla", "factura fiscala", "arve", "credit note", "hyvityslasku")  # fmt: skip

LEGAL_FORMS = ("oy", "oyj", "ay", "ky", "ab", "hb", "kb", "gmbh", "ag", "kg", "ohg", "ug", "e k", "sas", "sarl",
               "sa", "sasu", "eurl", "bv", "b v", "nv", "n v", "vof", "srl", "s r l", "spa", "s p a", "snc",
               "sl", "s l", "sa", "slu", "sp z o o", "spolka z o o", "s a", "lda", "unipessoal lda", "sro", "s r o",
               "as", "a s", "aps", "a s", "asa", "ltd", "limited", "plc", "llp", "llc", "inc", "dac", "kft", "zrt",
               "ou", "as", "uab", "sia", "d o o", "doo", "ad", "eood", "ood", "a g", "ev", "e v", "eg", "e g", "gbr",
               "se", "kgaa", "partg", "mbb", "co kg", "co", "eurl", "sci", "scop", "cooperatie", "stiftung")  # fmt: skip

# Line item table columns.
COLUMNS: dict[str, tuple[str, ...]] = {
    "description": (
        "description", "item", "items", "product", "service", "article", "details", "particulars", "designation",
        "tuote", "nimike", "kuvaus", "selite", "tuotenimi", "palvelu", "beskrivning", "artikel", "benamning",
        "vara", "tjanst", "bezeichnung", "beschreibung", "leistung", "artikelbezeichnung", "position",
        "designation", "libelle", "description", "produit", "omschrijving", "artikel", "product",
        "descrizione", "articolo", "prodotto", "servizio", "descripcion", "concepto", "producto", "articulo",
        "opis", "nazwa", "nazwa towaru", "towar", "usluga", "descricao", "produto", "artigo", "servico",
        "popis", "polozka", "nazev", "beskrivelse", "vare", "tekst", "megnevezes", "denumire",
    ),
    "quantity": (
        "qty", "quantity", "qnt", "units", "no", "kpl", "maara", "antal", "ant", "menge", "anzahl", "anz",
        "quantite", "qte", "aantal", "aant", "quantita", "qta", "cantidad", "cant", "ilosc", "quantidade",
        "qtd", "mnozstvi", "pocet", "pocet ks", "ks", "stk", "antall", "mennyiseg", "cantitate", "kogus", "q ta",
        "pcs", "pieces", "kpl", "st", "szt",
    ),
    "unit": ("unit", "uom", "yks", "yksikko", "enhet", "einheit", "eh", "unite", "eenheid", "unita", "um",
             "unidad", "ud", "jednostka", "jm", "j m", "unidade", "mj", "merna jednotka", "enhed"),
    "unit_price": (
        "unit price", "price", "rate", "unit cost", "price each", "a hinta", "a-hinta", "yksikkohinta", "hinta",
        "a pris", "pris", "styckpris", "enhetspris", "einzelpreis", "e preis", "preis", "stuckpreis",
        "prix unitaire", "prix", "p u", "pu ht", "prix unitaire ht", "stukprijs", "prijs", "prijs per stuk",
        "prezzo", "prezzo unitario", "prezzo unit", "precio", "precio unitario", "precio unit",
        "cena", "cena jedn", "cena jednostkowa", "cena netto", "preco", "preco unitario", "preco unit",
        "jednotkova cena", "jedn cena", "cena za mj", "cena za jednotku", "cena jedn netto", "stykpris", "enhedspris", "egysegar", "pret unitar",
    ),
    "vat_rate": ("vat", "vat %", "tax", "tax %", "vat rate", "alv", "alv %", "moms", "moms %", "mwst", "ust", "umsatzsteuer",
                 "steuer", "steuersatz", "mwst satz",
                 "ust %", "steuer", "tva", "taux tva", "btw", "btw %", "iva", "iva %", "aliquota", "dph",
                 "sazba dph", "stawka vat", "vat stawka", "stawka", "mva", "afa", "taxa iva", "arvonlisavero"),
    "amount": (
        "amount", "total", "line total", "net", "net amount", "sum", "summa", "yhteensa", "rivisumma",
        "hinta yht", "belopp", "summa", "betrag", "gesamt", "gesamtpreis", "summe", "montant", "total ht",
        "montant ht", "bedrag", "totaal", "importo", "totale", "importe", "total", "wartosc", "wartosc netto",
        "kwota", "valor", "total", "celkem", "castka", "cena celkem", "beløb", "belob", "osszeg", "valoare",
        "summa", "kokku",
    ),
}  # fmt: skip


@lru_cache(maxsize=64)
def phrase_regex(words: tuple[str, ...]) -> re.Pattern[str]:
    # Spaces in a phrase also match dots and runs of spaces ("p.u.", "Nr.  Rechnung").
    alternatives = "|".join(
        re.escape(norm(w).replace(".", " ")).replace("\\ ", "[\\s.]+")
        for w in sorted(set(words), key=len, reverse=True)
    )
    return re.compile(rf"(?<![a-z0-9])(?:{alternatives})(?![a-z0-9])")


# Totals that mean "amount still to pay" (may exclude prepayments) vs the gross invoice total.
TOTAL_DUE = ("amount due", "total due", "balance due", "due payable", "to pay", "amount payable", "zahlbetrag",
             "zu zahlen", "zu zahlender betrag", "noch zu zahlen", "restbetrag", "net a payer", "reste a payer",
             "maksettava", "att betala", "te betalen", "do zaplaty", "k uhrade", "at betale", "a pagar", "da pagare")  # fmt: skip
TOTAL_GROSS = ("grand total", "total amount", "invoice total", "rechnungsbetrag", "bruttosumme", "gesamtbetrag",
               "rechnungssumme", "endbetrag", "total ttc", "montant ttc", "totaalbedrag", "importo totale",
               "total factura", "razem brutto", "total com iva", "yhteensa", "summa", "totalt", "celkem")  # fmt: skip
