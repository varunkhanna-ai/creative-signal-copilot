"""W3.6 (§5 Job B): interpretable decision tree over the longevity proxy.

Feature set, exclusions, depth cap, and the rule-wording rule are decision-log
Entry #17. The deliverable is not the model — it is **rules a human can read
as sentences**, every one of which stays descriptive.

Trains on Tier-3 only (F1), which does not exist yet (B1). The module refuses
to fit on too little data rather than producing an accuracy figure that means
nothing.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from creativesignal.sources.curated import DB_PATH

MAX_DEPTH = 3
MIN_SAMPLES_LEAF = 5
MIN_TRAINING_ROWS = 30
TREE_PNG = Path("eval/results/insight_tree.png")
IMPORTANCE_PNG = Path("eval/results/feature_importance.png")

# Vocabularies shared with the reviewer so "offer language" means the same
# thing in an insight rule as it does in a policy flag.
OFFER_TERMS = ("discount", "% off", "sale", "free shipping", "bundle", "save",
               "limited stock", "deal", "offer")
INGREDIENT_TERMS = ("retinol", "niacinamide", "hyaluronic", "ceramide", "vitamin c",
                    "spf", "peptide", "salicylic", "glycolic", "collagen")
AUTHORITY_TERMS = ("dermatologist", "clinically", "lab", "tested", "proven",
                   "science", "expert", "recommended")

# Words that would turn a prevalence statement into a performance claim.
BANNED_IN_RULES = ("performs", "perform", "works", "converts", "wins", "winning",
                   "drives", "best", "effective", "successful", "outperform")


class InsufficientTreeData(RuntimeError):
    """Raised rather than fitting a tree nobody should trust."""


@dataclass
class TreeRule:
    """One root-to-leaf path, as conditions plus its leaf composition."""

    conditions: list[str]
    predicted_bucket: str
    n_samples: int
    n_matching: int

    @property
    def support(self) -> float:
        return self.n_matching / self.n_samples if self.n_samples else 0.0


@dataclass
class TreeResult:
    model: object = None
    feature_names: list[str] = field(default_factory=list)
    rules: list[TreeRule] = field(default_factory=list)
    accuracy: float = 0.0
    n_rows: int = 0
    class_balance: dict[str, int] = field(default_factory=dict)


# --- features -------------------------------------------------------------


def platform_count(value: str | None) -> int:
    """Number of placement surfaces in an Ad Library platform list.

    "FACEBOOK,INSTAGRAM,MESSENGER" -> 3. Unknown -> 0.
    """
    if not value or str(value).strip().lower() == "unknown":
        return 0
    return len([p for p in str(value).split(",") if p.strip()])


def _has_any(text: str, terms: tuple[str, ...]) -> int:
    lowered = (text or "").lower()
    return int(any(term in lowered for term in terms))


def build_features(rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Turn creative+annotation rows into the Entry #17 feature dicts."""
    features = []
    for row in rows:
        copy = f"{row.get('headline') or ''} {row.get('body_copy') or ''}"
        features.append(
            {
                "hook_type": row.get("hook_type") or "unknown",
                "tone": row.get("tone") or "unknown",
                # `platform` is a comma-separated Ad Library placement list
                # ("FACEBOOK,INSTAGRAM,MESSENGER"). One-hot encoding the raw
                # string makes every *combination* its own sparse class and
                # renders unreadably in a rule. The interpretable signal is
                # how many surfaces the ad was placed on — a breadth-of-buy
                # proxy. See Entry #27.
                "platform_count": platform_count(row.get("platform")),
                "headline_length": len((row.get("headline") or "").split()),
                "body_length": len((row.get("body_copy") or "").split()),
                "has_offer_language": _has_any(copy, OFFER_TERMS),
                "has_ingredient_mention": _has_any(copy, INGREDIENT_TERMS),
                "has_authority_language": _has_any(copy, AUTHORITY_TERMS),
            }
        )
    names = list(features[0]) if features else []
    return features, names


def load_training_rows(db_path: Path = DB_PATH) -> list[dict]:
    """Tier-3 rows with a proxy bucket, joined to their latest annotation."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return [
            dict(row)
            for row in conn.execute(
                "SELECT c.creative_id, c.headline, c.body_copy, c.platform, "
                "       c.proxy_bucket, a.hook_type, a.tone "
                "FROM creatives c LEFT JOIN annotations a "
                "  ON a.creative_id = c.creative_id "
                "WHERE c.source_type = 'tier3' AND c.proxy_bucket IS NOT NULL"
            )
        ]


# --- training -------------------------------------------------------------


def train_tree(rows: list[dict], max_depth: int = MAX_DEPTH) -> TreeResult:
    """Fit the depth-capped tree. Refuses on too little or single-class data."""
    from collections import Counter

    import pandas as pd
    from sklearn.tree import DecisionTreeClassifier

    if len(rows) < MIN_TRAINING_ROWS:
        raise InsufficientTreeData(
            f"{len(rows)} Tier-3 rows with a proxy bucket, need >= "
            f"{MIN_TRAINING_ROWS}. Tier-3 curation (W0.3) is outstanding — see "
            "docs/decision-log.md B1."
        )
    labels = [row["proxy_bucket"] for row in rows]
    balance = Counter(labels)
    if len(balance) < 2:
        raise InsufficientTreeData(
            f"Only one proxy bucket present ({list(balance)}). Nothing to split on. "
            "Re-check the Entry #5 thresholds against the real distribution."
        )

    features, _ = build_features(rows)
    frame = pd.get_dummies(pd.DataFrame(features))
    model = DecisionTreeClassifier(
        max_depth=max_depth,
        min_samples_leaf=MIN_SAMPLES_LEAF,
        class_weight="balanced",
        random_state=20260828,
    )
    model.fit(frame, labels)
    return TreeResult(
        model=model,
        feature_names=list(frame.columns),
        rules=extract_rules(model, list(frame.columns)),
        accuracy=float(model.score(frame, labels)),
        n_rows=len(rows),
        class_balance=dict(balance),
    )


def extract_rules(model, feature_names: list[str]) -> list[TreeRule]:
    """Walk each root-to-leaf path into a TreeRule."""
    tree = model.tree_
    rules: list[TreeRule] = []

    def walk(node: int, conditions: list[str]) -> None:
        if tree.children_left[node] == -1:  # leaf
            counts = tree.value[node][0]
            best = int(counts.argmax())
            rules.append(
                TreeRule(
                    conditions=list(conditions),
                    predicted_bucket=str(model.classes_[best]),
                    n_samples=int(tree.n_node_samples[node]),
                    n_matching=int(round(counts[best] * tree.n_node_samples[node] / counts.sum()))
                    if counts.sum()
                    else 0,
                )
            )
            return
        name = feature_names[tree.feature[node]]
        threshold = tree.threshold[node]
        walk(tree.children_left[node], conditions + [f"NOT {name}"
             if threshold == 0.5 else f"{name} <= {threshold:.1f}"])
        walk(tree.children_right[node], conditions + [f"{name}"
             if threshold == 0.5 else f"{name} > {threshold:.1f}"])

    walk(0, [])
    return rules


# --- the honesty-bearing part: rules as sentences ------------------------


# The one place performance vocabulary is allowed, because it is being
# negated. Held as a constant so the banned-word check can be applied to the
# *generated* clause without tripping over this fixed, reviewed sentence.
DISCLAIMER = (
    "This is a spend-persistence pattern in this corpus, not evidence that "
    "this combination performs better."
)


def _humanize(condition: str) -> str:
    negated = condition.startswith("NOT ")
    text = condition.removeprefix("NOT ").replace("_", " ")

    # Numeric features read as phrases, not as expressions. Handled before the
    # categorical rules below, which would otherwise turn "platform count <= 4"
    # into the ungrammatical "platform is count <= 4".
    m = re.match(r"^platform count (<=|>) ([\d.]+)$", text)
    if m:
        op, value = m.group(1), float(m.group(2))
        n = int(value)  # thresholds land on .5; floor gives the inclusive bound
        return (
            f"the ad runs on {n} or fewer placement surfaces"
            if op == "<=" else
            f"the ad runs on more than {n} placement surfaces"
        )
    m = re.match(r"^(headline|body) length (<=|>) ([\d.]+)$", text)
    if m:
        field, op, value = m.group(1), m.group(2), float(m.group(3))
        n = int(value)
        return (
            f"the {field} is {n} words or fewer"
            if op == "<=" else
            f"the {field} is longer than {n} words"
        )

    text = re.sub(r"^hook type ", "hook is ", text)
    text = re.sub(r"^tone ", "tone is ", text)
    text = re.sub(r"^platform ", "platform is ", text)
    text = text.replace("has offer language", "uses offer language")
    text = text.replace("has ingredient mention", "names an ingredient")
    text = text.replace("has authority language", "uses authority language")
    if negated:
        text = re.sub(r"^(hook|tone|platform) is ", r"\1 is not ", text) \
            if re.match(r"^(hook|tone|platform) is ", text) else f"not {text}"
    return text


def rule_claim(rule: TreeRule) -> str:
    """The descriptive half of a rule sentence — no disclaimer attached."""
    conditions = " and ".join(_humanize(c) for c in rule.conditions) or "all ads"
    direction = {
        "high": "longer",
        "mid": "for a moderate period",
        "low": "for a shorter period",
    }.get(rule.predicted_bucket, "for an unrecorded period")
    return (
        f"Among the {rule.n_samples} curated ads where {conditions}, "
        f"{rule.n_matching} fall in the {rule.predicted_bucket} longevity-proxy "
        f"bucket — meaning the advertiser kept running them {direction}."
    )


def rule_to_sentence(rule: TreeRule) -> str:
    """Render one rule as a prevalence sentence. Never a performance claim.

    The proxy is named as a proxy, and the closing clause stating what it is
    *not* is mandatory — see Entry #17.
    """
    return f"{rule_claim(rule)} {DISCLAIMER}"


def rules_as_sentences(result: TreeResult) -> list[str]:
    return [rule_to_sentence(rule) for rule in result.rules]


# --- exports --------------------------------------------------------------


def save_tree_plot(result: TreeResult, path: Path = TREE_PNG) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.tree import plot_tree

    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(16, 8))
    plot_tree(
        result.model,
        feature_names=result.feature_names,
        class_names=list(result.model.classes_),
        filled=True,
        rounded=True,
        fontsize=8,
        ax=ax,
    )
    ax.set_title("Longevity-proxy tree (descriptive, not causal)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_importance_plot(result: TreeResult, path: Path = IMPORTANCE_PNG) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    pairs = sorted(
        zip(result.feature_names, result.model.feature_importances_),
        key=lambda p: p[1],
        reverse=True,
    )[:12]
    names = [p[0] for p in reversed(pairs)]
    values = [p[1] for p in reversed(pairs)]

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(names, values, color="#0F6B5C")
    ax.set_xlabel("Relative split importance (not effect size)")
    ax.set_title("Which features the tree splits on")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def main() -> None:
    rows = load_training_rows()
    try:
        result = train_tree(rows)
    except InsufficientTreeData as exc:
        print(f"REFUSED TO TRAIN: {exc}")
        return
    print(f"trained on {result.n_rows} rows; balance {result.class_balance}")
    print(f"in-sample accuracy {result.accuracy:.2f} (directional, small sample)\n")
    for sentence in rules_as_sentences(result):
        print(f"  - {sentence}\n")
    print(f"tree -> {save_tree_plot(result)}")
    print(f"importance -> {save_importance_plot(result)}")


if __name__ == "__main__":
    main()
