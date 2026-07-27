from graph.nodes.migration import run_migration

sample_ddl = """
CREATE TABLE Author (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE Book (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    authorId INT NOT NULL,
    FOREIGN KEY (authorId) REFERENCES Author(id)
) ENGINE=InnoDB;
"""

result = run_migration(sample_ddl, "nosql")
print(f"Validation passed: {result['validation_passed']}")
print(f"\nMongo schema collections: {list(result['mongo_schema'].keys())}")
print(f"\nEmbed/reference notes:")
for note in result["embed_vs_reference_notes"]:
    print(f"- {note}")



print("\n" + "=" * 60)
print("REVERSE DIRECTION: NoSQL -> SQL")
print("=" * 60)

sample_mongo_schema = """
{
  "User": {
    "bsonType": "object",
    "required": ["_id", "username", "email"],
    "properties": {
      "_id": {"bsonType": "objectId"},
      "username": {"bsonType": "string"},
      "email": {"bsonType": "string"}
    }
  },
  "Post": {
    "bsonType": "object",
    "required": ["_id", "title", "authorId"],
    "properties": {
      "_id": {"bsonType": "objectId"},
      "title": {"bsonType": "string"},
      "content": {"bsonType": "string"},
      "authorId": {"bsonType": "objectId"}
    }
  }
}
"""

reverse_result = run_migration(sample_mongo_schema, "sql")
print(f"Validation passed: {reverse_result['validation_passed']}")
if reverse_result["validation_errors"]:
    for err in reverse_result["validation_errors"]:
        print(f"ERROR: {err}")
print(f"\nGenerated DDL:\n{reverse_result['sql_ddl']}")
print(f"\nNormalization notes:")
for note in reverse_result.get("normalization_notes", []):
    print(f"- {note}")