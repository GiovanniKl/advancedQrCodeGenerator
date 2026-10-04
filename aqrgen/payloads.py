"""Standard QR code message formats: Wi-Fi, contact, payment, etc.

Each message type is a dataclass. Its fields describe the inputs of the
"Insert" form (label, hint, kind of input) and its ``build`` method
returns the text to encode, after checking the inputs. Errors are
raised as `ValueError` with a user-readable message.
"""

import dataclasses
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import ClassVar
from urllib.parse import quote

CZ_PREFIX_WEIGHTS = (10, 5, 8, 4, 2, 1)
"""Checksum weights of the prefix of a Czech account number."""

CZ_NUMBER_WEIGHTS = (6, 3, 7, 9, 10, 5, 8, 4, 2, 1)
"""Checksum weights of the base of a Czech account number."""

EPC_MAX_BYTES = 331
"""Largest allowed size of an EPC (SEPA) payment code."""


def field(label, default="", *, kind="entry", hint="", options=()):
    """Declare a payload field together with its form input.

    Parameters
    ----------
    label : str
        Label of the input in the form.
    default : str or bool, default ""
        Initial value.
    kind : {"entry", "text", "choice", "check"}, default "entry"
        Single-line entry, multi-line text, dropdown or checkbox.
    hint : str, default ""
        Gray help text shown next to the input.
    options : tuple of str, default ()
        Choices of a dropdown.

    Returns
    -------
    dataclasses.Field
        The dataclass field.
    """
    return dataclasses.field(
        default=default,
        metadata={
            "label": label,
            "kind": kind,
            "hint": hint,
            "options": options,
        },
    )


class Payload:
    """Base class of the message types."""

    title: ClassVar[str] = ""
    """Name of the message type in the Insert menu."""

    note: ClassVar[str] = ""
    """Extra explanation shown at the top of the form."""

    def build(self):
        """Return the text to encode in the QR code.

        Returns
        -------
        str
            The formatted message.
        """
        raise NotImplementedError


# --- helpers ---------------------------------------------------------


def _required(value, label):
    """Return a stripped value, or complain that it is missing.

    Parameters
    ----------
    value : str
        Input value.
    label : str
        Name of the input, used in the error message.

    Returns
    -------
    str
        The value without surrounding whitespace.

    Raises
    ------
    ValueError
        If the value is empty.
    """
    value = value.strip()
    if not value:
        raise ValueError(f"Please fill in: {label}.")
    return value


def _max_length(value, length, label):
    """Complain if a value is too long.

    Parameters
    ----------
    value : str
        Input value.
    length : int
        Largest allowed number of characters.
    label : str
        Name of the input, used in the error message.

    Returns
    -------
    str
        The value.

    Raises
    ------
    ValueError
        If the value is longer than allowed.
    """
    if len(value) > length:
        raise ValueError(f"{label} can have at most {length} characters.")
    return value


def phone_number(value, label="Phone number"):
    """Normalize a phone number.

    Parameters
    ----------
    value : str
        Number as typed, spaces, dashes, dots and parentheses allowed.
    label : str, default "Phone number"
        Name of the input, used in the error message.

    Returns
    -------
    str
        Digits with an optional leading ``+``.

    Raises
    ------
    ValueError
        If the result is not 3 to 15 digits.
    """
    number = re.sub(r"[\s\-.()/]", "", _required(value, label))
    if number.startswith("00"):
        number = "+" + number[2:]
    if not re.fullmatch(r"\+?\d{3,15}", number):
        raise ValueError(
            f"{label} {value.strip()!r} is not valid, e.g. +420 123 456 789."
        )
    return number


def _escape(value, characters):
    r"""Escape characters with a backslash.

    Parameters
    ----------
    value : str
        Text to escape.
    characters : str
        Characters to escape; the backslash itself is always escaped.

    Returns
    -------
    str
        The escaped text; line breaks become ``\n``.
    """
    value = value.replace("\\", "\\\\")
    for character in characters:
        value = value.replace(character, "\\" + character)
    return value.replace("\r\n", "\n").replace("\n", "\\n")


def _amount(value, label, maximum):
    """Parse a money amount.

    Parameters
    ----------
    value : str
        Amount as typed; spaces and a decimal comma are allowed.
    label : str
        Name of the input, used in the error message.
    maximum : decimal.Decimal
        Largest allowed amount.

    Returns
    -------
    decimal.Decimal or None
        The amount with two decimals, or None if the input is empty.

    Raises
    ------
    ValueError
        If the amount is not a number with at most 2 decimals, or is
        not between 0.01 and the maximum.
    """
    text = re.sub(r"\s", "", value).replace(",", ".")
    if not text:
        return None
    try:
        amount = Decimal(text)
    except InvalidOperation:
        raise ValueError(f"{label} {value!r} is not a number.") from None
    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError(f"{label} can have at most 2 decimals.")
    if not Decimal("0.01") <= amount <= maximum:
        raise ValueError(f"{label} must be from 0.01 to {maximum}.")
    return amount.quantize(Decimal("0.01"))


def parse_date(value, label):
    """Parse a date typed as 2026-10-04 or 4.10.2026.

    Parameters
    ----------
    value : str
        Date as typed.
    label : str
        Name of the input, used in the error message.

    Returns
    -------
    datetime.date
        The date.

    Raises
    ------
    ValueError
        If the date can't be read.
    """
    text = re.sub(r"\s", "", value)
    for pattern in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            pass
    raise ValueError(
        f"{label} {value!r} is not a date, e.g. 2026-10-04 or 4.10.2026."
    )


def parse_time(value, label):
    """Parse a time typed as 18:30 or 18.30.

    Parameters
    ----------
    value : str
        Time as typed.
    label : str
        Name of the input, used in the error message.

    Returns
    -------
    tuple of int
        Hours and minutes.

    Raises
    ------
    ValueError
        If the time can't be read.
    """
    match = re.fullmatch(r"(\d{1,2})[:.](\d{2})", value.strip())
    if not match or int(match[1]) > 23 or int(match[2]) > 59:
        raise ValueError(f"{label} {value!r} is not a time, e.g. 18:30.")
    return int(match[1]), int(match[2])


def iban(value):
    """Normalize and check an IBAN.

    Parameters
    ----------
    value : str
        IBAN as typed, spaces allowed.

    Returns
    -------
    str
        The IBAN in capitals without spaces.

    Raises
    ------
    ValueError
        If the format or the check digits are wrong.
    """
    text = re.sub(r"\s", "", value).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", text):
        raise ValueError(f"{value.strip()!r} is not an IBAN.")
    rearranged = text[4:] + text[:4]
    digits = "".join(str(int(character, 36)) for character in rearranged)
    if int(digits) % 97 != 1:
        raise ValueError(f"IBAN {value.strip()!r} has wrong check digits.")
    return text


def czech_account_to_iban(value):
    """Convert a Czech account number like 19-2000145399/0800 to IBAN.

    Parameters
    ----------
    value : str
        Account number as ``[prefix-]number/bank code``.

    Returns
    -------
    str
        The IBAN.

    Raises
    ------
    ValueError
        If the format or a checksum of the account number is wrong.
    """
    match = re.fullmatch(
        r"(?:(\d{1,6})-)?(\d{2,10})/(\d{4})", re.sub(r"\s", "", value)
    )
    if not match:
        raise ValueError(
            f"{value.strip()!r} is not a Czech account number, e.g. "
            "19-2000145399/0800."
        )
    prefix = (match[1] or "").zfill(6)
    number = match[2].zfill(10)
    for digits, weights in (
        (prefix, CZ_PREFIX_WEIGHTS),
        (number, CZ_NUMBER_WEIGHTS),
    ):
        if sum(int(d) * w for d, w in zip(digits, weights, strict=True)) % 11:
            raise ValueError(
                f"Account number {value.strip()!r} has a wrong checksum."
            )
    bban = match[3] + prefix + number
    check = 98 - int(bban + "123500") % 97  # "CZ00" as digits
    return f"CZ{check:02d}{bban}"


def account_or_iban(value):
    """Accept an IBAN or a Czech account number.

    Parameters
    ----------
    value : str
        IBAN or ``[prefix-]number/bank code``.

    Returns
    -------
    str
        The IBAN.

    Raises
    ------
    ValueError
        If neither format matches or a check fails.
    """
    value = _required(value, "Account (IBAN or Czech account number)")
    if "/" in value:
        return czech_account_to_iban(value)
    return iban(value)


# --- message types ---------------------------------------------------


@dataclasses.dataclass
class Wifi(Payload):
    """Wi-Fi network: phones offer to join it."""

    title: ClassVar[str] = "Wi-Fi network"
    ssid: str = field("Network name (SSID)")
    password: str = field("Password")
    security: str = field(
        "Security",
        "WPA/WPA2/WPA3",
        kind="choice",
        options=("WPA/WPA2/WPA3", "WEP", "None (open network)"),
    )
    hidden: bool = field("Hidden network", False, kind="check")

    def build(self):
        """Return a ``WIFI:`` message.

        Returns
        -------
        str
            The formatted message.
        """
        special = ';,:"'
        if not self.ssid:
            raise ValueError("Please fill in: Network name (SSID).")
        ssid = _escape(self.ssid, special)
        kind = {"WPA/WPA2/WPA3": "WPA", "WEP": "WEP"}.get(
            self.security, "nopass"
        )
        parts = [f"T:{kind}", f"S:{ssid}"]
        if kind != "nopass":
            if not self.password:
                raise ValueError("Please fill in: Password.")
            parts.append("P:" + _escape(self.password, special))
        if self.hidden:
            parts.append("H:true")
        return "WIFI:" + ";".join(parts) + ";;"


def _vcard_text(value):
    """Escape a vCard text value.

    Parameters
    ----------
    value : str
        Text as typed.

    Returns
    -------
    str
        The stripped text with backslashes, commas and semicolons
        escaped.
    """
    return _escape(value.strip(), ",;")


@dataclasses.dataclass
class Contact(Payload):
    """Contact card (vCard 3.0): phones offer to save it."""

    title: ClassVar[str] = "Contact"
    first_name: str = field("First name")
    last_name: str = field("Last name")
    phone: str = field("Phone", hint="e.g. +420 123 456 789")
    email: str = field("E-mail")
    organization: str = field("Company / organization")
    job_title: str = field("Job title")
    website: str = field("Website")
    street: str = field("Street")
    city: str = field("City")
    postal_code: str = field("Postal code")
    country: str = field("Country")

    def build(self):
        """Return a vCard.

        Returns
        -------
        str
            The formatted message.
        """
        first, last = self.first_name.strip(), self.last_name.strip()
        if not (first or last or self.organization.strip()):
            raise ValueError("Please fill in a name or a company.")

        lines = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"N:{_vcard_text(last)};{_vcard_text(first)};;;",
            f"FN:{_vcard_text(' '.join(filter(None, (first, last))))}"
            if first or last
            else f"FN:{_vcard_text(self.organization)}",
        ]
        if self.organization.strip():
            lines.append(f"ORG:{_vcard_text(self.organization)}")
        if self.job_title.strip():
            lines.append(f"TITLE:{_vcard_text(self.job_title)}")
        if self.phone.strip():
            lines.append(f"TEL:{phone_number(self.phone)}")
        if self.email.strip():
            lines.append(f"EMAIL:{self.email.strip()}")
        if self.website.strip():
            lines.append(f"URL:{self.website.strip()}")
        address = (self.street, self.city, self.postal_code, self.country)
        if any(part.strip() for part in address):
            street, city, postal, country = (
                _vcard_text(part) for part in address
            )
            lines.append(f"ADR:;;{street};{city};;{postal};{country}")
        lines.append("END:VCARD")
        return "\n".join(lines)


@dataclasses.dataclass
class Email(Payload):
    """E-mail: phones open a pre-filled e-mail."""

    title: ClassVar[str] = "E-mail"
    address: str = field("To (e-mail address)")
    subject: str = field("Subject")
    body: str = field("Text", kind="text")

    def build(self):
        """Return a ``mailto:`` link.

        Returns
        -------
        str
            The formatted message.
        """
        address = _required(self.address, "To (e-mail address)")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", address):
            raise ValueError(f"{address!r} is not an e-mail address.")
        query = "&".join(
            f"{key}={quote(value.strip())}"
            for key, value in (("subject", self.subject), ("body", self.body))
            if value.strip()
        )
        return f"mailto:{address}" + (f"?{query}" if query else "")


@dataclasses.dataclass
class Sms(Payload):
    """Text message: phones open a pre-filled SMS."""

    title: ClassVar[str] = "SMS"
    number: str = field("Phone number", hint="e.g. +420 123 456 789")
    text: str = field("Text", kind="text")

    def build(self):
        """Return an ``SMSTO:`` message.

        Returns
        -------
        str
            The formatted message.
        """
        return f"SMSTO:{phone_number(self.number)}:{self.text.strip()}"


@dataclasses.dataclass
class Phone(Payload):
    """Phone number: phones offer to call it."""

    title: ClassVar[str] = "Phone call"
    number: str = field("Phone number", hint="e.g. +420 123 456 789")

    def build(self):
        """Return a ``tel:`` link.

        Returns
        -------
        str
            The formatted message.
        """
        return f"tel:{phone_number(self.number)}"


@dataclasses.dataclass
class WhatsApp(Payload):
    """WhatsApp message: opens a chat with a pre-filled message."""

    title: ClassVar[str] = "WhatsApp message"
    note: ClassVar[str] = (
        "Leave the number empty to let the person pick the recipient."
    )
    number: str = field(
        "Phone number with country code", hint="e.g. +420 123 456 789"
    )
    text: str = field("Message", kind="text")

    def build(self):
        """Return a ``wa.me`` link.

        Returns
        -------
        str
            The formatted message.
        """
        path = ""
        if self.number.strip():
            number = phone_number(self.number)
            if not number.startswith("+"):
                raise ValueError(
                    "Enter the number with its country code, e.g. "
                    "+420 123 456 789."
                )
            path = number[1:]
        text = self.text.strip()
        if not path and not text:
            raise ValueError("Please fill in a phone number or a message.")
        return f"https://wa.me/{path}" + (
            f"?text={quote(text)}" if text else ""
        )


@dataclasses.dataclass
class Location(Payload):
    """Place on a map: phones open it in a maps app."""

    title: ClassVar[str] = "Location"
    note: ClassVar[str] = (
        "Fill in coordinates, or an address or place name to search for."
    )
    latitude: str = field("Latitude", hint="e.g. 49.1951")
    longitude: str = field("Longitude", hint="e.g. 16.6068")
    place: str = field("or address / place name")
    link: str = field(
        "Link type",
        "Google Maps link (all phones)",
        kind="choice",
        options=(
            "Google Maps link (all phones)",
            "geo: link (default maps app, mostly Android)",
        ),
    )

    def build(self):
        """Return a maps link or a ``geo:`` URI.

        Returns
        -------
        str
            The formatted message.
        """
        place = self.place.strip()
        coordinates = None
        if self.latitude.strip() or self.longitude.strip():
            coordinates = (
                self._coordinate(self.latitude, "Latitude", 90),
                self._coordinate(self.longitude, "Longitude", 180),
            )
        elif not place:
            raise ValueError("Please fill in coordinates or a place.")
        if self.link.startswith("geo:"):
            if coordinates:
                return f"geo:{coordinates[0]},{coordinates[1]}"
            return f"geo:0,0?q={quote(place)}"
        query = f"{coordinates[0]},{coordinates[1]}" if coordinates else place
        return "https://www.google.com/maps/search/?api=1&query=" + quote(
            query, safe=","
        )

    @staticmethod
    def _coordinate(value, label, limit):
        """Parse a latitude or longitude.

        Parameters
        ----------
        value : str
            Number as typed, a decimal comma is allowed.
        label : str
            Name of the input, used in the error message.
        limit : int
            Largest allowed absolute value.

        Returns
        -------
        str
            The number as text.

        Raises
        ------
        ValueError
            If it is not a number within the limit.
        """
        text = _required(value, label).replace(",", ".")
        try:
            number = float(text)
        except ValueError:
            raise ValueError(f"{label} {value!r} is not a number.") from None
        if abs(number) > limit:
            raise ValueError(f"{label} must be from -{limit} to {limit}.")
        return text


@dataclasses.dataclass
class Event(Payload):
    """Calendar event: phones offer to add it to the calendar."""

    title: ClassVar[str] = "Calendar event"
    summary: str = field("Title")
    start_date: str = field("Start date", hint="2026-10-04 or 4.10.2026")
    start_time: str = field("Start time", hint="18:30")
    end_date: str = field("End date", hint="empty = same day")
    end_time: str = field("End time", hint="empty = 1 hour later")
    all_day: bool = field("All-day event", False, kind="check")
    location: str = field("Place")
    description: str = field("Description", kind="text")

    def build(self):
        """Return an iCalendar ``VEVENT``.

        Returns
        -------
        str
            The formatted message.
        """
        summary = _required(self.summary, "Title")
        start_day = parse_date(
            _required(self.start_date, "Start date"), "Start date"
        )
        end_day = (
            parse_date(self.end_date, "End date")
            if self.end_date.strip()
            else start_day
        )
        if self.all_day:
            if end_day < start_day:
                raise ValueError("The event ends before it starts.")
            # the end date of all-day events is exclusive
            start = f"DTSTART;VALUE=DATE:{start_day:%Y%m%d}"
            end = f"DTEND;VALUE=DATE:{end_day + timedelta(days=1):%Y%m%d}"
        else:
            begin = datetime.combine(start_day, datetime.min.time()).replace(
                **_hours(self.start_time, "Start time")
            )
            if self.end_time.strip():
                finish = datetime.combine(end_day, datetime.min.time()).replace(
                    **_hours(self.end_time, "End time")
                )
            else:
                finish = begin + timedelta(hours=1)
            if finish < begin:
                raise ValueError("The event ends before it starts.")
            start = f"DTSTART:{begin:%Y%m%dT%H%M%S}"
            end = f"DTEND:{finish:%Y%m%dT%H%M%S}"
        lines = [
            "BEGIN:VEVENT",
            f"SUMMARY:{_escape(summary, ',;')}",
            start,
            end,
        ]
        if self.location.strip():
            lines.append(f"LOCATION:{_escape(self.location.strip(), ',;')}")
        if self.description.strip():
            lines.append(
                f"DESCRIPTION:{_escape(self.description.strip(), ',;')}"
            )
        lines.append("END:VEVENT")
        return "\n".join(lines)


def _hours(value, label):
    """Read a required time as keyword arguments for `datetime.replace`.

    Parameters
    ----------
    value : str
        Time as typed.
    label : str
        Name of the input, used in the error message.

    Returns
    -------
    dict
        ``hour`` and ``minute``.
    """
    hour, minute = parse_time(_required(value, label), label)
    return {"hour": hour, "minute": minute}


@dataclasses.dataclass
class CzPayment(Payload):
    """Czech QR Platba (SPAYD): banking apps pre-fill a payment."""

    title: ClassVar[str] = "Payment (CZ QR Platba)"
    account: str = field(
        "Account (IBAN or Czech account number)",
        hint="e.g. 19-2000145399/0800",
    )
    amount: str = field("Amount", hint="e.g. 480,50")
    currency: str = field(
        "Currency", "CZK", kind="choice", options=("CZK", "EUR")
    )
    variable_symbol: str = field("Variable symbol (VS)")
    specific_symbol: str = field("Specific symbol (SS)")
    constant_symbol: str = field("Constant symbol (KS)")
    message: str = field("Message for the recipient", hint="max. 60")
    recipient: str = field("Recipient name", hint="max. 35")
    due_date: str = field("Due date", hint="2026-10-04 or 4.10.2026")

    def build(self):
        """Return an ``SPD*1.0*`` payment string.

        Returns
        -------
        str
            The formatted message.
        """
        parts = ["SPD", "1.0", f"ACC:{account_or_iban(self.account)}"]
        amount = _amount(self.amount, "Amount", Decimal("9999999.99"))
        if amount is not None:
            parts.append(f"AM:{amount}")
        parts.append(f"CC:{self.currency}")
        if self.due_date.strip():
            day = parse_date(self.due_date, "Due date")
            parts.append(f"DT:{day:%Y%m%d}")
        for key, value, length in (
            ("MSG", self.message, 60),
            ("RN", self.recipient, 35),
        ):
            text = value.strip()
            if text:
                label = "Message" if key == "MSG" else "Recipient name"
                _max_length(text, length, label)
                parts.append(f"{key}:{text.replace('*', '%2A')}")
        for key, value, label in (
            ("X-VS", self.variable_symbol, "Variable symbol"),
            ("X-SS", self.specific_symbol, "Specific symbol"),
            ("X-KS", self.constant_symbol, "Constant symbol"),
        ):
            digits = value.strip()
            if digits:
                if not re.fullmatch(r"\d{1,10}", digits):
                    raise ValueError(f"{label} must be 1 to 10 digits.")
                parts.append(f"{key}:{digits}")
        return "*".join(parts)


@dataclasses.dataclass
class EuPayment(Payload):
    """EPC / GiroCode SEPA transfer in euros."""

    title: ClassVar[str] = "Payment (EU SEPA, EPC)"
    note: ClassVar[str] = (
        "Euro transfers within SEPA. Supported by many banking apps, "
        "e.g. in Germany, Austria, the Netherlands, Belgium and Finland."
    )
    name: str = field("Recipient name", hint="max. 70")
    account: str = field("IBAN")
    bic: str = field("BIC", hint="optional within the EEA")
    amount: str = field("Amount in EUR", hint="e.g. 12,50")
    reference: str = field(
        "Structured reference", hint="RF creditor reference; or use text"
    )
    text: str = field("Payment text", hint="max. 140")

    def build(self):
        """Return an EPC QR code text (version 002, UTF-8).

        Returns
        -------
        str
            The formatted message.
        """
        name = _max_length(
            _required(self.name, "Recipient name"), 70, "Recipient name"
        )
        account = iban(_required(self.account, "IBAN"))
        bic = re.sub(r"\s", "", self.bic).upper()
        if bic and not re.fullmatch(r"[A-Z0-9]{8}([A-Z0-9]{3})?", bic):
            raise ValueError(f"{self.bic.strip()!r} is not a BIC.")
        amount = _amount(self.amount, "Amount", Decimal("999999999.99"))
        reference = re.sub(r"\s", "", self.reference)
        text = self.text.strip()
        if reference and text:
            raise ValueError(
                "Use either a structured reference or a payment text."
            )
        _max_length(reference, 35, "Structured reference")
        _max_length(text, 140, "Payment text")
        lines = [
            "BCD",
            "002",
            "1",  # UTF-8
            "SCT",
            bic,
            name,
            account,
            f"EUR{amount}" if amount is not None else "",
            "",  # purpose code
            reference,
            text,
        ]
        while lines[-1] == "":
            lines.pop()
        result = "\n".join(lines)
        if len(result.encode("utf-8")) > EPC_MAX_BYTES:
            raise ValueError("The payment data is too long for an EPC code.")
        return result


PAYLOAD_TYPES = (
    Wifi,
    Contact,
    Email,
    Sms,
    Phone,
    WhatsApp,
    Location,
    Event,
    CzPayment,
    EuPayment,
)
"""Message types in the order of the Insert menu."""
