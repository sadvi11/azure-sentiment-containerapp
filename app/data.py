"""Small embedded training dataset for the sentiment model.

Kept in-repo on purpose so the model trains at Docker build time with no
external download. In production you would pull a labelled dataset from Azure
Blob Storage or a feature store; the training pipeline stays identical.
"""

# (text, label) pairs. label: 1 = positive, 0 = negative
TRAINING_DATA = [
    # positive
    ("this product is amazing and works perfectly", 1),
    ("absolutely love it, best purchase this year", 1),
    ("fast delivery and great customer service", 1),
    ("the support team was helpful and kind", 1),
    ("excellent quality, highly recommend", 1),
    ("works exactly as described, very happy", 1),
    ("smooth setup and great performance", 1),
    ("fantastic value for the money", 1),
    ("i am impressed with how reliable it is", 1),
    ("wonderful experience from start to finish", 1),
    ("the deployment was seamless and quick", 1),
    ("clean interface and easy to use", 1),
    ("super fast and responsive, well done", 1),
    ("great documentation made onboarding easy", 1),
    ("solid uptime and no issues so far", 1),
    ("customer support resolved my issue instantly", 1),
    ("beautiful design and intuitive controls", 1),
    ("this exceeded my expectations completely", 1),
    ("highly efficient and saves me time", 1),
    ("a delightful and polished product", 1),
    # negative
    ("this is terrible and broke after one day", 0),
    ("worst experience ever, do not buy", 0),
    ("slow, buggy and constantly crashing", 0),
    ("the support team ignored my request", 0),
    ("poor quality and overpriced", 0),
    ("it stopped working within a week", 0),
    ("frustrating setup and confusing docs", 0),
    ("waste of money, very disappointed", 0),
    ("the app keeps freezing and lagging", 0),
    ("horrible customer service, no help at all", 0),
    ("deployment failed repeatedly and wasted hours", 0),
    ("cluttered interface that is hard to use", 0),
    ("painfully slow and unresponsive", 0),
    ("missing features and full of errors", 0),
    ("constant downtime, totally unreliable", 0),
    ("support never resolved my problem", 0),
    ("ugly design and clunky navigation", 0),
    ("this fell far below my expectations", 0),
    ("inefficient and wastes my time daily", 0),
    ("a broken and unpolished mess", 0),
]
