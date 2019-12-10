-- start with influx -precision rfc3339
-- https://docs.influxdata.com/influxdb/v1.7/query_language/data_exploration/#time-syntax
-- https://docs.influxdata.com/influxdb/v1.7/tools/shell/#precision-rfc3339-h-m-s-ms-u-ns

show databases
use tendermint
show measurements
select * from tendermint_consensus_height;
show field keys from tendermint_consensus_height
show tag keys from tendermint_consensus_height
select * from tendermint_consensus_height limit 1;
select * from tendermint_consensus_height where node_id='node' limit 1;
select * from tendermint_consensus_height where node_id='node0' limit 1;
SELECT derivative(mean("gauge"), 1s) FROM "tendermint_consensus_height" WHERE time >= 1575390109065ms and time <= 1575390415761ms GROUP BY time(2s) fill(previous)
SELECT derivative(mean("gauge"), 1s) FROM "tendermint_consensus_height" WHERE time >= 1575390400000000000ms and time <= 1575390415761ms GROUP BY time(2s) fill(previous)
SELECT derivative(mean("gauge"), 1s) FROM "tendermint_consensus_height" WHERE time >= 1575390409065ms and time <= 1575390415761ms GROUP BY time(2s) fill(previous)
select gauge FROM "tendermint_consensus_height" WHERE time >= 1575390409065ms and time <= 1575390415761ms GROUP BY time(2s) fill(previous)
select gauge FROM "tendermint_consensus_height" WHERE time >= 1575390409065ms and time <= 1575390415761ms fill(previous)
SELECT derivative(mean("gauge"), 1s) FROM "tendermint_consensus_height" WHERE time >= 1575390360334ms and time <= 1575390365414ms GROUP BY time(50ms) fill(previous)
SELECT derivative(mean("gauge"), 1s) FROM "tendermint_consensus_height" WHERE time >= 1575390360334ms and time <= 1575390365414ms  fill(previous)
SELECT * FROM "tendermint_consensus_height" WHERE time >= 1575390360334ms and time <= 1575390365414ms  fill(previous)
SELECT * FROM "tendermint_consensus_height" WHERE time >= 1575390360334ms and time <= 1575390365414ms
SELECT * FROM "tendermint_consensus_height" WHERE time >= 1575390360334ms and time <= 1575390365414ms and node_id="node0"
SELECT * FROM "tendermint_consensus_height" WHERE time >= 1575390360334ms and time <= 1575390365414ms and node_id="node0";
SELECT * FROM "tendermint_consensus_height" WHERE time >= 1575390360334ms and time <= 1575390365414ms
SELECT * FROM "tendermint_consensus_height" WHERE time >= 1575390360334ms and time <= 1575390365414ms and node_id="node3"
SELECT * FROM "tendermint_consensus_height" WHERE time >= 1575390360334ms and time <= 1575390365414ms and node_id='node3'
SELECT * FROM "tendermint_consensus_height" WHERE time >= 1575390360334ms and time <= 1575391365414ms and node_id='node3'
SELECT * FROM "tendermint_consensus_height" WHERE time >= 1575390360334ms and time <= 1575390465414ms and node_id='node3'
exit
use tendermint
SELECT * FROM "tendermint_consensus_height" WHERE time >= 1575390360334ms and time <= 1575390465414ms and node_id='node3'
exit