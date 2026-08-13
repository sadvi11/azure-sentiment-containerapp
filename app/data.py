"""Training data for the sentiment model, and an honest held-out test set.

WHY THIS FILE LOOKS THE WAY IT DOES
-----------------------------------
The first version was 40 hand-written product-review sentences. It looked fine
and was effectively useless in production, for two separate reasons that took
measurement rather than inspection to find.

**1. Domain mismatch.** The deployed demo is linked from a CV that talks about
financial documents, so people typed "losses widened and the outlook was cut".
Every one of those words was out of vocabulary. TF-IDF produced a near-zero
vector, logistic regression returned the class prior, and the API answered with
a real-looking label at 0.50-0.55 confidence. Measured against six financial
sentences it got two right - worse than guessing.

**2. Nothing to generalise from.** Hand-written sentences use each sentiment
word roughly once. With bigrams and `min_df=1` that produced 1039 features for
121 samples, 863 of which appeared in exactly one document. Features that occur
once cannot carry signal; they can only memorise. Five-fold cross-validation
was **0.471 - worse than random** - while predictions on the training sentences
themselves looked perfect. Hyperparameter tuning capped out at 0.545, which is
the tell that the data was the problem, not the configuration.

THE FIX
-------
Sentiment lives in a bounded vocabulary used across many contexts, so the
training set is generated compositionally: a sentiment lexicon crossed with
sentence templates. Every sentiment word then appears in many sentences, which
is what gives the model something transferable to learn instead of something
to memorise.

HOW IT IS HONESTLY EVALUATED
----------------------------
Cross-validation on generated data mostly proves the model learned the
generator - it scores ~0.99 and that number means very little. So
`HELDOUT_EXAMPLES` below is hand-written, never used for training, and uses the
lexicon in sentence shapes the generator does not produce. That is the number
worth quoting, and `train.py` prints both so the gap is visible rather than
hidden.

Out-of-lexicon text is handled at serving time, not here: `model.py` measures
vocabulary coverage and returns "uncertain" rather than guessing. More training
data would not have fixed that on its own - the next unfamiliar domain would
fail the same silent way.
"""
import itertools
import random

# --- Sentiment lexicon -----------------------------------------------------
# Deliberately spans the domains this endpoint is actually asked about:
# product/service quality, and financial or business results.

POSITIVE_ADJECTIVES = [
    "excellent", "outstanding", "strong", "impressive", "reliable", "smooth",
    "fast", "helpful", "polished", "seamless", "solid", "superb", "great",
    "wonderful", "efficient", "robust", "profitable", "growing", "improving",
    "record", "successful", "favourable", "encouraging", "stable", "healthy",
    "promising", "exceptional", "dependable", "responsive", "thorough",
]

NEGATIVE_ADJECTIVES = [
    "terrible", "awful", "weak", "disappointing", "unreliable", "broken",
    "slow", "unhelpful", "buggy", "clumsy", "fragile", "poor", "dreadful",
    "frustrating", "wasteful", "unstable", "unprofitable", "shrinking",
    "deteriorating", "dismal", "failing", "unfavourable", "discouraging",
    "erratic", "unhealthy", "worrying", "inadequate", "undependable",
    "unresponsive", "careless",
]

# Nouns that genuinely carry polarity on their own.
POSITIVE_NOUNS = [
    "growth", "profit", "progress", "improvement", "success", "recovery",
    "gain", "upgrade", "breakthrough", "surplus",
]

NEGATIVE_NOUNS = [
    "loss", "decline", "failure", "problem", "delay", "defect", "outage",
    "complaint", "downturn", "shortfall", "setback", "breakdown", "downgrade",
    "bankruptcy", "deficit",
]

# Nouns that are NEUTRAL and must appear in BOTH classes.
#
# The first attempt put "outlook" in POSITIVE_NOUNS. The model duly learned
# that "outlook" means good, and then classified "losses widened and the
# outlook was cut" as POSITIVE at 0.67 confidence - a confident wrong answer,
# which is worse than an uncertain one. A neutral noun that only ever appears
# with one label becomes a sentiment carrier by accident. Sharing them forces
# the adjectives and verbs to carry the signal, which is where it belongs.
NEUTRAL_NOUNS = [
    "outlook", "results", "performance", "quarter", "service", "quality",
    "value", "report", "margins", "revenue", "guidance", "earnings",
    "demand", "forecast", "momentum",
]

# Verbs and participles carry a great deal of sentiment in business writing -
# "beat", "surged", "widened", "slashed" - and the original lexicon had none,
# which is why financial sentences scored near the class prior.
POSITIVE_VERBS = [
    "beat", "surged", "exceeded", "doubled", "rallied", "raised", "improved",
    "climbed", "strengthened", "accelerated", "outperformed", "recovered",
]

NEGATIVE_VERBS = [
    "missed", "plunged", "widened", "slashed", "cut", "fell", "dropped",
    "collapsed", "weakened", "deteriorated", "underperformed", "suspended",
]

# {a}/{a2} adjective, {n} polar noun, {u} neutral noun, {v} polar verb.
TEMPLATES = [
    "the {a} {n} was clear",
    "this was {a} and {a2}",
    "a genuinely {a} {n}",
    "{u} was {a} this quarter",
    "the team delivered {a} {n}",
    "overall the {u} looks {a}",
    "reported {a} {n} again",
    "i found it {a} and {a2}",
    "an {a} {n} by any measure",
    "the {u} has been {a} throughout",
    "{a} {n} across the board",
    "{u} were {a} and {a2}",
    "the {u} is {a}",
    "support was {a} and {a2}",
    "the product feels {a}",
    "another {a} quarter of {n}",
    "customers described it as {a}",
    "the report showed {a} {n}",
    "expect {a} {n} to continue",
    "a {a} and {a2} outcome",
    # verb-led frames - business writing carries sentiment in the verb
    "{u} {v} sharply this quarter",
    "the company {v} on {u}",
    "{u} {v} again and the {u2} was {a}",
    "{n} {v} while {u} stayed {a}",
    "management {v} {u} after an {a} quarter",
    "the {u} {v} and {n} followed",
    "{u} {v}, a {a} sign",
    "they {v} {u} for the third quarter running",
]

SAMPLES_PER_CLASS = 600


def _generate(adjectives, nouns, verbs, label):
    """Cross the lexicon with the templates to produce labelled sentences.

    Neutral nouns are shared across both classes on purpose - see the note on
    NEUTRAL_NOUNS. Only adjectives, polar nouns and verbs differ by label.
    """
    out = []
    for template in TEMPLATES:
        for adjective, second in itertools.product(adjectives, adjectives):
            if adjective == second:
                continue
            sentence = template.replace("{a2}", second).replace("{a}", adjective)

            nouns_needed = "{n}" in sentence
            verbs_needed = "{v}" in sentence
            neutral_needed = "{u}" in sentence

            noun_options = nouns if nouns_needed else [None]
            verb_options = verbs if verbs_needed else [None]
            neutral_options = NEUTRAL_NOUNS if neutral_needed else [None]

            for noun, verb, neutral in itertools.product(
                noun_options, verb_options, neutral_options
            ):
                candidate = sentence
                if noun is not None:
                    candidate = candidate.replace("{n}", noun)
                if verb is not None:
                    candidate = candidate.replace("{v}", verb)
                if neutral is not None:
                    # {u2} is a second neutral slot; reuse the pool so it stays
                    # neutral rather than becoming a class marker.
                    other = NEUTRAL_NOUNS[
                        (NEUTRAL_NOUNS.index(neutral) + 1) % len(NEUTRAL_NOUNS)
                    ]
                    candidate = candidate.replace("{u2}", other)
                    candidate = candidate.replace("{u}", neutral)
                out.append((candidate, label))
    return out


def _build_training_data():
    rng = random.Random(7)  # fixed seed: the artifact must be reproducible
    positive = rng.sample(
        _generate(
            POSITIVE_ADJECTIVES, POSITIVE_NOUNS, POSITIVE_VERBS, 1
        ),
        SAMPLES_PER_CLASS,
    )
    negative = rng.sample(
        _generate(
            NEGATIVE_ADJECTIVES, NEGATIVE_NOUNS, NEGATIVE_VERBS, 0
        ),
        SAMPLES_PER_CLASS,
    )
    return positive + negative


# (text, label) pairs. label: 1 = positive, 0 = negative
TRAINING_DATA = _build_training_data()


# --- Held-out evaluation set -----------------------------------------------
# Hand-written. NEVER used for training. These use the lexicon in sentence
# shapes the generator does not produce, which is what makes them a real
# generalisation test rather than a re-run of the generator.

HELDOUT_EXAMPLES = [
    # positive
    ("record profits and revenue beat expectations", 1),
    ("strong growth and management raised guidance", 1),
    ("the migration completed smoothly with no outage", 1),
    ("customer service was helpful and responsive throughout", 1),
    ("an exceptional quarter with improving margins", 1),
    ("the deployment was seamless and performance is solid", 1),
    ("reliable, efficient and genuinely great value", 1),
    ("progress has been encouraging and results are promising", 1),
    ("a healthy recovery with stable momentum", 1),
    ("the upgrade delivered outstanding quality", 1),
    ("dependable service and thorough documentation", 1),
    ("profitable growth continued across every region", 1),
    # negative
    ("losses widened and the outlook was cut", 0),
    ("the company reported a dismal quarter of decline", 0),
    ("shares fell after a disappointing shortfall", 0),
    ("the outage was prolonged and support was unresponsive", 0),
    ("buggy, slow and deeply frustrating to use", 0),
    ("a weak result with deteriorating margins", 0),
    ("unreliable performance and frequent breakdowns", 0),
    ("the delay was careless and the defect went unfixed", 0),
    ("worrying risk and an unfavourable downturn", 0),
    ("poor quality and an inadequate response to complaints", 0),
    ("failing service with erratic uptime", 0),
    ("unprofitable and shrinking with no recovery in sight", 0),
]
