from app.services.decision_maker_rules import is_decision_maker_title
from app.services.web_search import guess_person_title_from_title


def main() -> None:
    examples_accept = [
        "Jane Doe - CEO - Acme | LinkedIn",
        "Jane Doe - CEO - Acme | Facebook",
        "Jane Doe - CEO - Acme | Instagram",
        "John Smith - Founder - Example Co | LinkedIn",
        "A B - Owner - Widgets LLC | LinkedIn",
        "C D - President - My Company | LinkedIn",
        "E F - Managing Director - My Company | LinkedIn",
        "G H - General Manager - My Company | LinkedIn",
        "I J - Senior Head of Sales - My Company | LinkedIn",
        "K L - Head of Growth - My Company | LinkedIn",
        "M N - Director - My Company | LinkedIn",
        "O P - Senior Director - My Company | LinkedIn",
        "Q R - VP, Sales - My Company | LinkedIn",
        "S T - Vice President - My Company | LinkedIn",
        "U V - SVP Marketing - My Company | LinkedIn",
        "W X - Senior Vice President - My Company | LinkedIn",
    ]
    for raw in examples_accept:
        title = guess_person_title_from_title(raw) or ""
        ok, kw = is_decision_maker_title(title)
        assert ok, (raw, title, kw)

    examples_reject = [
        "Jane Doe - Executive Assistant to CEO - Acme | LinkedIn",
        "Jane Doe - Executive Assistant to CEO - Acme | Facebook",
        "John Smith - Customer Support Specialist - Example Co | LinkedIn",
        "A B - Sales Representative - Widgets LLC | LinkedIn",
        "C D - Intern - My Company | LinkedIn",
        "E F - Receptionist - My Company | LinkedIn",
        "G H - Coordinator - My Company | LinkedIn",
        "I J - Technician - My Company | LinkedIn",
    ]
    for raw in examples_reject:
        title = guess_person_title_from_title(raw) or ""
        ok, kw = is_decision_maker_title(title)
        assert not ok, (raw, title, kw)


if __name__ == "__main__":
    main()
    print("OK")
