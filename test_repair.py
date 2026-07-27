"""
Tests the retry-with-repair logic by directly feeding invoke_llm_json
a prompt that's likely to produce slightly malformed JSON on the
first try (asking for something oddly specific), to see the repair
loop actually kick in.
"""

from graph.llm import invoke_llm_json

# Deliberately awkward prompt to increase chance of a malformed first pass
result = invoke_llm_json("""
Return a JSON object with a field "numbers" containing the first 5
prime numbers as a list, and a field "note" containing a string with
an embedded double-quote character in it, like: he said "hello".
Respond with ONLY the JSON object, no other text.
""")

print(result)