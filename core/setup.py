from pymongo.errors import CollectionInvalid

from .mongo.connections import MongoCollections, mongo_client, db_name
from .mongo.drugs import DrugsFields
from .neo4j.ogm import RefersTo, ArgotNode, DrugNode

def database_setup():
    collections = MongoCollections()
    default_db = mongo_client()[db_name]
    collection_names = [
        collections.channels.name,
        collections.messages.name,
        collections.posts.name,
        collections.analysis_jobs.name,
    ]
    for collection_name in collection_names:
        try:
            default_db.create_collection(collection_name)
        except CollectionInvalid:
            pass

    collections.channels.create_index([
        ("channel_id", 1),
        ("username", 1),
        ("title", 1)
    ], unique=True)

    collections.messages.create_index([
        ("message_id", 1),
        ("channel_id", 1),
        ("edit_date", 1),
    ], unique=True)

    collections.analysis_jobs.create_index(
        [("status", 1)],
        unique=True,
        partialFilterExpression={"status": "accepting_request"}
    )

    collections.analysis_jobs.create_index(
        [("post_ids", 1)],
        unique=True, # 유일성을 보장한다.
        partialFilterExpression={ # 하지만 아래 조건을 만족하는 문서에만 적용한다.
            "status": {
                "$in": [
                    "accepting_request",
                    "pending",
                    "submitted",
                    "processed"
                    # FAILED와 COMPLETED 상태는 여기서 제외
                ]
            }
        }
    )

    collections.drugs.create_index(
        [
            ("drugbank_id", 1),
        ],
        unique=True,
    )



    for drugs in collections.drugs.find():
        for argot in drugs.get(DrugsFields.argots, []):
            RefersTo.merge(
                argot=ArgotNode(name=argot.get("name"), description=argot.get("description")),
                drug=DrugNode(
                    drugbank_id=drugs.get(DrugsFields.drugbank_id),
                    name=drugs.get(DrugsFields.name),
                    english_name=drugs.get(DrugsFields.english_name),
                    drug_type=drugs.get(DrugsFields.drug_type),
                ),
            )