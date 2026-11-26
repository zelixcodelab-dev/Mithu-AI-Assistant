from app.language import detect_language


def test_detects_malayalam():
    assert detect_language("എന്റെ admission status എന്താണ്?") == "ml"


def test_detects_manglish():
    assert detect_language("ente admission status entha") == "manglish"


def test_defaults_to_english():
    assert detect_language("Please explain the application process") == "en"


def test_explicit_language():
    assert detect_language("hello", "ml") == "ml"
