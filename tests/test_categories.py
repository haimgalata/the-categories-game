from src.categories import load_categories, normalize_category


def test_load_categories_returns_list():
    cats = load_categories()
    assert isinstance(cats, list)
    assert "City" in cats


def test_load_categories_returns_copy():
    cats1 = load_categories()
    cats2 = load_categories()

    cats1.append("NewCategory")

    assert "NewCategory" not in cats2


def test_normalize_category_basic():
    assert normalize_category("  City  ") == "city"


def test_normalize_category_spaces():
    assert normalize_category("  Sports   Team ") == "sports team"


def test_normalize_category_invalid_input():
    assert normalize_category(None) == ""
