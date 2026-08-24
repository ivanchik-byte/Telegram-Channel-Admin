"""Static consistency checks for the i18n dictionaries.

The usage-vs-defined test is an AST scan over src/ — it would have caught
the missing 'action_cancelled' key that shipped to production.
"""
import ast
import pathlib

from src.core.i18n import TRANSLATIONS

SRC_DIR = pathlib.Path(__file__).resolve().parent.parent / "src"


def _collect_defined_keys():
    source = (SRC_DIR / "core" / "i18n.py").read_text()
    tree = ast.parse(source)
    keys_by_lang = {}
    current_lang = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value in ("ru", "en") and isinstance(v, ast.Dict):
                    current_lang = k.value
                    keys_by_lang[current_lang] = {
                        sub.value for sub in v.keys
                        if isinstance(sub, ast.Constant)
                    }
    return keys_by_lang


def _collect_used_keys():
    used = set()
    for path in SRC_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "i18n"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                used.add(node.args[0].value)
    return used


class TestI18nConsistency:
    def test_every_used_key_is_defined(self):
        defined = _collect_defined_keys()
        all_defined = set().union(*defined.values())
        used = _collect_used_keys()
        missing = used - all_defined
        assert not missing, f"i18n.get() uses undefined keys: {sorted(missing)}"

    def test_ru_en_parity(self):
        by_lang = _collect_defined_keys()
        ru_only = by_lang["ru"] - by_lang["en"]
        en_only = by_lang["en"] - by_lang["ru"]
        assert not ru_only, f"keys missing in 'en': {sorted(ru_only)}"
        assert not en_only, f"keys missing in 'ru': {sorted(en_only)}"

    def test_no_placeholder_mismatch_between_langs(self):
        """{placeholder} sets must match between ru and en for every key."""
        import re
        by_lang = _collect_defined_keys()
        # re-parse values this time
        source = (SRC_DIR / "core" / "i18n.py").read_text()
        ns = {}
        exec(compile(ast.parse(source), "<i18n>", "exec"), ns)  # noqa: S102
        translations = ns["TRANSLATIONS"]
        for key in translations["ru"]:
            ru_ph = set(re.findall(r"\{(\w+)\}", translations["ru"].get(key, "")))
            en_ph = set(re.findall(r"\{(\w+)\}", translations["en"].get(key, "")))
            assert ru_ph == en_ph, f"placeholder mismatch for '{key}': ru={ru_ph}, en={en_ph}"

    def test_translations_object_fallback(self):
        from src.core.i18n import i18n
        # unknown key falls back to the key name itself, never raises
        assert i18n.get("__no_such_key__") == "__no_such_key__"

    def test_set_language_ignores_unknown(self):
        from src.core.i18n import i18n
        before = i18n.lang
        i18n.set_language("de")  # unsupported language must be ignored
        assert i18n.lang == before
