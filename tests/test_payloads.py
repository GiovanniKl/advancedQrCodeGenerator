"""Tests of the standard message formats."""

import dataclasses

import pytest

from aqrgen import payloads as p

# --- helpers ---------------------------------------------------------


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("+420 123 456 789", "+420123456789"),
        ("00420-123-456-789", "+420123456789"),
        ("(603) 123.456", "603123456"),
    ],
)
def test_phone_number(typed, expected):
    assert p.phone_number(typed) == expected


@pytest.mark.parametrize("typed", ["", "12", "+420 12a", "1" * 16])
def test_invalid_phone_number(typed):
    with pytest.raises(ValueError, match="Phone number"):
        p.phone_number(typed)


@pytest.mark.parametrize(
    "value",
    ["DE89 3704 0044 0532 0130 00", "gb82west12345698765432"],
)
def test_valid_iban(value):
    assert p.iban(value) == value.replace(" ", "").upper()


@pytest.mark.parametrize(
    ("value", "message"),
    [("DE89 3704 0044 0532 0130 01", "check digits"), ("12345", "not an")],
)
def test_invalid_iban(value, message):
    with pytest.raises(ValueError, match=message):
        p.iban(value)


def test_czech_account_to_iban():
    # example from the Czech National Bank's IBAN documentation
    assert (
        p.czech_account_to_iban("19-2000145399/0800")
        == "CZ6508000000192000145399"
    )


def test_czech_account_without_prefix_gives_valid_iban():
    result = p.czech_account_to_iban("2000145399/0800")
    assert p.iban(result) == result


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("19-2000145398/0800", "checksum"),
        ("18-2000145399/0800", "checksum"),
        ("2000145399", "not a Czech account"),
    ],
)
def test_invalid_czech_account(value, message):
    with pytest.raises(ValueError, match=message):
        p.czech_account_to_iban(value)


@pytest.mark.parametrize("typed", ["2026-10-04", "4.10.2026", "4. 10. 2026"])
def test_parse_date(typed):
    assert f"{p.parse_date(typed, 'Date'):%Y%m%d}" == "20261004"


def test_every_type_has_a_title_and_labeled_fields():
    for payload_type in p.PAYLOAD_TYPES:
        assert payload_type.title
        for f in dataclasses.fields(payload_type):
            assert f.metadata["label"]
            if f.metadata["kind"] == "choice":
                assert f.default in f.metadata["options"]


# --- message types ---------------------------------------------------


def test_wifi():
    assert (
        p.Wifi(ssid="Home", password="secret").build()
        == "WIFI:T:WPA;S:Home;P:secret;;"
    )


def test_wifi_escapes_special_characters():
    text = p.Wifi(ssid="My;Net", password='a:b"c,d\\').build()
    assert text == 'WIFI:T:WPA;S:My\\;Net;P:a\\:b\\"c\\,d\\\\;;'


def test_open_hidden_wifi():
    text = p.Wifi(
        ssid="Cafe", security="None (open network)", hidden=True
    ).build()
    assert text == "WIFI:T:nopass;S:Cafe;H:true;;"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [({"password": "x"}, "SSID"), ({"ssid": "Home"}, "Password")],
)
def test_wifi_missing(kwargs, message):
    with pytest.raises(ValueError, match=message):
        p.Wifi(**kwargs).build()


def test_contact():
    text = p.Contact(
        first_name="Jan",
        last_name="Novák",
        phone="+420 123 456 789",
        email="jan@example.com",
        organization="ACME; s.r.o.",
        city="Brno",
    ).build()
    lines = text.split("\n")
    assert lines[:2] == ["BEGIN:VCARD", "VERSION:3.0"]
    assert "N:Novák;Jan;;;" in lines
    assert "FN:Jan Novák" in lines
    assert "TEL:+420123456789" in lines
    assert "ORG:ACME\\; s.r.o." in lines
    assert "ADR:;;;Brno;;;" in lines
    assert lines[-1] == "END:VCARD"


def test_contact_needs_a_name():
    with pytest.raises(ValueError, match="name"):
        p.Contact(phone="123456").build()


def test_email():
    text = p.Email(
        address="a@b.cz", subject="Hi there", body="Line 1\nLine 2"
    ).build()
    assert text == "mailto:a@b.cz?subject=Hi%20there&body=Line%201%0ALine%202"
    assert p.Email(address="a@b.cz").build() == "mailto:a@b.cz"


def test_invalid_email():
    with pytest.raises(ValueError, match="not an e-mail"):
        p.Email(address="nobody").build()


def test_sms_and_phone():
    assert (
        p.Sms(number="+420 777 000 111", text="Hello").build()
        == "SMSTO:+420777000111:Hello"
    )
    assert p.Phone(number="+420 777 000 111").build() == "tel:+420777000111"


def test_whatsapp():
    text = p.WhatsApp(number="+420 777 000 111", text="Ahoj, jak se máš?")
    assert text.build() == (
        "https://wa.me/420777000111?text=Ahoj%2C%20jak%20se%20m%C3%A1%C5%A1%3F"
    )
    assert p.WhatsApp(text="Hi").build() == "https://wa.me/?text=Hi"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [({"number": "777000111"}, "country code"), ({}, "phone number or")],
)
def test_whatsapp_invalid(kwargs, message):
    with pytest.raises(ValueError, match=message):
        p.WhatsApp(**kwargs).build()


def test_location():
    google = p.Location(latitude="49,1951", longitude="16.6068").build()
    assert google == (
        "https://www.google.com/maps/search/?api=1&query=49.1951,16.6068"
    )
    geo = p.Location(
        latitude="49.1951", longitude="16.6068", link="geo: link"
    ).build()
    assert geo == "geo:49.1951,16.6068"
    place = p.Location(place="Špilberk, Brno").build()
    assert place.endswith("query=%C5%A0pilberk,%20Brno")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({}, "coordinates or a place"),
        ({"latitude": "95", "longitude": "10"}, "Latitude must"),
        ({"latitude": "45", "longitude": "east"}, "not a number"),
    ],
)
def test_location_invalid(kwargs, message):
    with pytest.raises(ValueError, match=message):
        p.Location(**kwargs).build()


def test_event():
    text = p.Event(
        summary="Party; at mine",
        start_date="4.10.2026",
        start_time="18:30",
        location="Brno",
    ).build()
    assert text.split("\n") == [
        "BEGIN:VEVENT",
        "SUMMARY:Party\\; at mine",
        "DTSTART:20261004T183000",
        "DTEND:20261004T193000",  # one hour by default
        "LOCATION:Brno",
        "END:VEVENT",
    ]


def test_all_day_event_end_is_exclusive():
    text = p.Event(
        summary="Trip",
        start_date="2026-10-04",
        end_date="2026-10-05",
        all_day=True,
    ).build()
    assert "DTSTART;VALUE=DATE:20261004" in text
    assert "DTEND;VALUE=DATE:20261006" in text


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"start_date": "2026-10-04", "start_time": "18:00"}, "Title"),
        ({"summary": "x", "start_time": "18:00"}, "Start date"),
        (
            {"summary": "x", "start_date": "2026-10-04", "start_time": "25:00"},
            "not a time",
        ),
        (
            {
                "summary": "x",
                "start_date": "2026-10-04",
                "start_time": "18:00",
                "end_time": "17:00",
            },
            "ends before",
        ),
    ],
)
def test_event_invalid(kwargs, message):
    with pytest.raises(ValueError, match=message):
        p.Event(**kwargs).build()


def test_cz_payment():
    text = p.CzPayment(
        account="19-2000145399/0800",
        amount="1 480,5",
        variable_symbol="1234567890",
        message="Platba * za zboží",
        due_date="31.12.2026",
    ).build()
    assert text == (
        "SPD*1.0*ACC:CZ6508000000192000145399*AM:1480.50*CC:CZK"
        "*DT:20261231*MSG:Platba %2A za zboží*X-VS:1234567890"
    )


def test_cz_payment_minimal_with_iban():
    text = p.CzPayment(account="CZ65 0800 0000 1920 0014 5399").build()
    assert text == "SPD*1.0*ACC:CZ6508000000192000145399*CC:CZK"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({}, "Account"),
        ({"account": "19-2000145399/0800", "amount": "1.234"}, "2 decimals"),
        ({"account": "19-2000145399/0800", "amount": "0"}, "from 0.01"),
        ({"account": "19-2000145399/0800", "variable_symbol": "12a"}, "digits"),
        ({"account": "19-2000145399/0800", "message": "x" * 61}, "at most 60"),
    ],
)
def test_cz_payment_invalid(kwargs, message):
    with pytest.raises(ValueError, match=message):
        p.CzPayment(**kwargs).build()


def test_eu_payment():
    text = p.EuPayment(
        name="Franz Mustermänn",
        account="DE89 3704 0044 0532 0130 00",
        bic="BHBLDEHHXXX",
        amount="12,3",
        text="Gelegenheit",
    ).build()
    assert text.split("\n") == [
        "BCD",
        "002",
        "1",
        "SCT",
        "BHBLDEHHXXX",
        "Franz Mustermänn",
        "DE89370400440532013000",
        "EUR12.30",
        "",
        "",
        "Gelegenheit",
    ]


def test_eu_payment_minimal_drops_empty_tail():
    text = p.EuPayment(name="A", account="DE89370400440532013000").build()
    assert text.split("\n") == [
        "BCD",
        "002",
        "1",
        "SCT",
        "",
        "A",
        "DE89370400440532013000",
    ]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"account": "DE89370400440532013000"}, "Recipient name"),
        ({"name": "A", "account": "DE00"}, "not an IBAN"),
        (
            {
                "name": "A",
                "account": "DE89370400440532013000",
                "reference": "RF18539007547034",
                "text": "x",
            },
            "either",
        ),
        (
            {"name": "A", "account": "DE89370400440532013000", "bic": "X"},
            "not a BIC",
        ),
    ],
)
def test_eu_payment_invalid(kwargs, message):
    with pytest.raises(ValueError, match=message):
        p.EuPayment(**kwargs).build()
