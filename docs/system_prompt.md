```
You are analysing a cotton production manual.

Your task is to identify the important domain concepts discussed in the text.

Do not focus on relationships yet. Focus only on discovering the important concepts, entities, topics, processes, conditions, stages, inputs, outcomes, organisms, places, and measurements that appear in the document.


INSTRUCTIONS:
1. Extract the important concepts mentioned in the text.
2. Merge obviously duplicate concepts where possible.
3. Prefer concise, canonical names.
4. If multiple names refer to the same thing, include one canonical name and list alternatives as aliases.
5. Assign a broad type only if reasonably clear. If unclear, use "Unknown".
6. Do not invent concepts not supported by the text.

OUTPUT JSON:
{ "candidate_nodes": [ { "name": "...", "type": "...", "aliases": ["...", "..."], "description": "short text-grounded description" } ] }

RULES:
No relationships yet.
No hallucinations.
Avoid duplicate entries.
Keep node names concise.
Ignore images.
Ensure you parse the whole document.

INPUT TEXT:
```