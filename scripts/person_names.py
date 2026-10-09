"""Name handling shared by the parser and the database identity layer.

The sheets print "FAMILY Given", and the same name can arrive from different meets
in slightly different shapes. Splitting a printed name into as_person columns and
deciding which existing person it refers to are pure text rules with no database
access, so they live here rather than inside the ingest scripts: `ingest_routines`
uses them while parsing, and `routine_identity` uses the same keys to find the
person it should link a result row to. Keeping one implementation is what stops the
parser and the writer from disagreeing about who "LIN Isabella Jr" is.

Nothing here touches the database, and nothing here mutates its argument.
"""

import re
from typing import Any, Dict, List, Optional

# Tokens that share the Swimmer column but are not part of the name.
#
# 'YANOVSKIS Milana 12u' was checked with pdfplumber word offsets before deciding this:
# the name ends at x=191.73 and '12u' starts at x=196.47, i.e. it is a separate column
# bleeding into the line, so it is not the swimmer's name. Division markers printed
# after a hyphen ('LIN - 18/19 Isabella', 'MCKEEVER - SR Paige') are the meet's block
# name and are dropped too.
_NON_NAME_TOKEN_RE = re.compile(
    r"""^(?:
          \d{1,2}\s*[uU](?![a-z])      # 12u, 10U
        | \d{1,2}\s*[-/&]\s*\d{1,2}    # 18/19, 11-12
        | \d{1,2}\s*&\s*(?:under|over) # 10 & Under
        | u\s*&\s*under
        )$""",
    re.X,
)
_DIVISION_WORDS = {"YOUTH", "JUNIOR", "NOVICE", "INTERMEDIATE", "AGE", "GROUP",
                   "SR", "JR", "PRELIM", "FINAL", "TECHNICAL"}
_GENERATION_SUFFIXES = {"JR", "SR"}

# 'KIM-12U' -> 'KIM' + dropped '12U'. The age group is welded onto the surname here
# rather than sitting in its own column.
_WELDED_AGE_SUFFIX_RE = re.compile(
    r"^(?P<base>[^\W\d_][\w'.-]*?)\s*-\s*(?P<age>\d{1,2}\s*[uU](?![a-z]))$", re.I
)




def split_person_name(printed: str) -> Dict[str, Any]:
    """Decompose a printed PDF name into as_person columns.

    The sheets print "FAMILY Given", sometimes with a middle initial
    ("AKHROMTSEV Michaella J"), a generational suffix ("MILLER Lillian Jr"), a
    two-word surname ("ALDANA MARTINEZ Valeria") or a parenthetical second name
    ("HUANG Rosalyn (xiaoxin)").

    `printed` is always returned verbatim. Nothing is dropped from it, because
    team_athletes and as_result_person_link.athlete_name are the PDF's lineage and
    the only place the original can be recovered from.

    The generational suffix is pulled out into its own column rather than being
    appended to given_name, and person_match_keys() keeps it in the lookup key.
    Four same-club pairs in the corpus print as "LIN Isabella" / "LIN Isabella Jr" /
    "LIN Isabella Sr" and "MILLER Lillian" / "Jr" / "Sr"; collapsing the suffix
    would merge a parent and a child into one person and silently average two
    swimmers' scores together. Splitting one person into two records is
    recoverable; merging two people is not.
    """
    raw = (printed or "").strip()
    out: Dict[str, Any] = {
        "printed": raw,
        "family_name": None,
        "given_name": None,
        "middle_name": None,
        "suffix": None,
        "alt_name": None,
        "dropped_tokens": [],
    }
    if not raw:
        return out

    alt = re.findall(r"\(([^)]*)\)", raw)
    if alt:
        out["alt_name"] = " ".join(a.strip() for a in alt if a.strip()) or None
    core = re.sub(r"\([^)]*\)", " ", raw)

    tokens = [t for t in core.split() if t]
    kept: List[str] = []
    after_hyphen = False
    for token in tokens:
        bare = token.strip("-").upper()
        if token.strip() == "-":
            after_hyphen = True
            continue
        # Some sheets weld the age group onto the surname with a hyphen:
        # 'KIM-12U Olivia', 'YANOVSKIS-12U Milana'. The suffix belongs to the age
        # column, not the family name, so split it off before anything else.
        welded = _WELDED_AGE_SUFFIX_RE.match(token)
        if welded:
            out["dropped_tokens"].append(welded.group("age"))
            token = welded.group("base")
            bare = token.strip("-").upper()
            if not token:
                continue
        if _NON_NAME_TOKEN_RE.match(token):
            out["dropped_tokens"].append(token)
            continue
        if bare in _DIVISION_WORDS and (after_hyphen or bare not in _GENERATION_SUFFIXES):
            out["dropped_tokens"].append(token)
            continue
        kept.append(token)

    if not kept:
        # Nothing survived the filter. The printed form is all we have, so keep it
        # whole rather than inventing an empty person.
        out["given_name"] = raw
        return out

    suffix = None
    if len(kept) > 1 and kept[-1].upper() in _GENERATION_SUFFIXES:
        suffix = kept[-1].upper()
        out["suffix"] = suffix
        kept = kept[:-1]

    middle = None
    # A single trailing letter is a middle initial ('JINA Sara J'), not a given name.
    if len(kept) > 2 and len(kept[-1]) == 1 and kept[-1].isalpha():
        middle = kept[-1]
        kept = kept[:-1]

    # The sheets print "FAMILY Given", so the LAST kept token is the given name and
    # everything before it is the surname - which may itself be two words
    # ('ALDANA MARTINEZ Valeria'). Joining kept[1:] would push the second half of a
    # two-word surname into the given name.
    out["given_name"] = kept[-1]
    out["middle_name"] = middle
    if len(kept) > 1:
        out["family_name"] = " ".join(kept[:-1])
    return out


def person_match_keys(printed: str) -> List[str]:
    """Lookup keys for a person, in priority order.

    Exact printed form first, then family/given reversed: a person may have been
    created from another sheet that printed the parts the other way round.

    A generational suffix is treated as part of the identity, never as noise. The
    corpus contains same-club 'LIN Isabella' / 'LIN Isabella Jr' / 'LIN Isabella Sr'
    and 'MILLER Lillian' / 'Jr' / 'Sr'. A suffix-free fallback would let a Jr resolve
    to the Sr or to the parent, so a suffix-bearing name only ever matches on
    suffix-bearing keys and is reported as a distinct person.
    """
    parts = split_person_name(printed)
    family = (parts["family_name"] or "").strip()
    given = (parts["given_name"] or "").strip()
    if not family and not given:
        return []

    def norm(*bits: str) -> str:
        return " ".join(" ".join(b for b in bits if b).lower().split())

    keys: List[str] = []
    if parts["suffix"]:
        # Every key carries the suffix, including the reversed one, or a Jr would
        # still reach the parent through 'isabella lin'.
        qualified = norm(given, parts["suffix"])
        keys.append(norm(family, qualified))
        keys.append(norm(family + " " + parts["suffix"], given))
        keys.append(norm(qualified, family))
    else:
        keys.append(norm(family, given))
        if parts["middle_name"]:
            keys.append(norm(family, given + " " + parts["middle_name"]))
            keys.append(norm(family + " " + parts["middle_name"], given))
        reversed_key = norm(given, family)
        if reversed_key not in keys:
            keys.append(reversed_key)

    seen = set()
    return [k for k in keys if k and not (k in seen or seen.add(k))]


def person_column_values(printed: str) -> Dict[str, Any]:
    """The as_person columns for one printed name.

    as_person has no suffix column, so a generational suffix is folded back onto
    given_name. Dropping it instead would make 'LIN Isabella', 'LIN Isabella Jr' and
    'LIN Isabella Sr' three identical rows and silently average a parent and a child
    into one person on the next import. The suffix-free and suffix-bearing forms
    therefore stay distinguishable in the database, which is what person_match_keys()
    relies on.

    Printed lineage is deliberately not represented here: team_athletes and
    as_result_person_link.athlete_name keep the PDF's exact wording, including any age
    group, because that is the only place the original can be recovered from.
    """
    parts = split_person_name(printed)
    given = parts["given_name"]
    if parts["suffix"]:
        given = f"{given} {parts['suffix']}" if given else parts["suffix"]
    return {
        "family_name": parts["family_name"],
        "given_name": given or parts["printed"],
        "middle_name": parts["middle_name"],
    }


def person_keys_from_columns(family_name: Optional[str], given_name: Optional[str],
                             middle_name: Optional[str] = None) -> List[str]:
    """Lookup keys for a person row already in the database.

    The mirror image of person_match_keys(): it turns stored columns back into keys so
    an existing person can be found by the same keys a printed name produces. Both
    sides must agree, so the two functions are kept next to each other on purpose.
    """
    family = (family_name or "").strip()
    given = (given_name or "").strip()
    middle = (middle_name or "").strip()
    if not family and not given:
        return []

    def norm(*bits: str) -> str:
        return " ".join(" ".join(b for b in bits if b).lower().split())

    keys = [norm(family, given)]
    if middle:
        keys.append(norm(family, given + " " + middle))
        keys.append(norm(family + " " + middle, given))
    keys.append(norm(given, family))
    seen = set()
    return [k for k in keys if k and not (k in seen or seen.add(k))]
