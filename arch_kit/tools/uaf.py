"""uaf.py - the meanings the UAF grid gives its cells.

Each constant below is the UAF grid's own meaning of a view id, not a project's choice. A project can
rename its views, but the grid cell that holds capabilities is still the capability taxonomy.
A project's own choices (which views are required, where a generated section lives) are declared
under `views` in the declaration, and are not here.
"""

# St-Tx: the Strategic Taxonomy, the cell that lists the capabilities.
CAPABILITY_TAXONOMY = "St-Tx"
# Rs-Tr: the Resources Traceability cell, which ties the resources and functions to operational activities.
TRACEABILITY = "Rs-Tr"
# Op-Pr: the Operational Processes cell, the activities.
OPERATIONAL_PROCESSES = "Op-Pr"
# Rs-Pr: the Resources Processes cell, the functions.
RESOURCE_PROCESSES = "Rs-Pr"
