"""NV Local single-city pipeline definition."""

from pipelines.node.note_taker import note_taker_chain
from pipelines.node.run_agent_team import run_agent_team_chain
from pipelines.node.summary_writer import summary_writer_chain

chain = run_agent_team_chain | note_taker_chain | summary_writer_chain
