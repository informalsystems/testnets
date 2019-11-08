% General notes from running the tmtestnet.py stack
% Adi Seredinschi <adi@interchain.io>
% November 7, 2019


### Error 1: ssh-keygen

- triggered from tmtestnet.py:1856
- fixed itself: the error did not appear after two runs
- did not save the logs


### Warning 1: ssh-keygen

- Relevant log segment:
```
2019-11-07 11:43:20,683 INFO    Monitoring successfully deployed
2019-11-07 11:43:20,690 DEBUG   Removing any existing keys for host: ec2-3-83-97-136.compute-1.amazonaws.com
2019-11-07 11:43:21,700 DEBUG   Scanning keys for host: ec2-3-83-97-136.compute-1.amazonaws.com
2019-11-07 11:43:21,857 WARNING ssh-keyscan failed with return code -13 and 0 keys - trying again in 5 seconds
2019-11-07 11:43:26,863 DEBUG   Scanning keys for host: ec2-3-83-97-136.compute-1.amazonaws.com
2019-11-07 11:43:28,394 DEBUG   Created folder: /Users/adi/.tmtestnet/4-trial/tendermint/validators
2019-11-07 11:43:28,398 DEBUG   Wrote configuration to /Users/adi/.tmtestnet/4-trial/tendermint/validators/terraform-extra-vars.yaml
2019-11-07 11:43:28,398 INFO    Deploying Tendermint node group: validators
2019-11-07 11:43:28,398 INFO    Executing command: ansible-playbook -e @/Users/adi/.tmtestnet/4-trial/tendermint/validators/terraform-extra-vars.yaml ansible-terraform.yaml
```

- this run eventually resulted in an error (see next subsection)

### Error 2

- Log:
```
2019-11-07 11:45:05,432 ERROR   Failed to execute "network deploy" for configuration file: runs/4-trial/nets.yaml
2019-11-07 11:45:05,432 ERROR   sequence entries are not allowed here
  in "/Users/adi/.tmtestnet/4-trial/tendermint/validators/output-vars.yaml", line 2, column 22
Traceback (most recent call last):
  File "./tmtestnet.py", line 392, in tmtestnet
    fn(cfg, **kwargs)
  File "./tmtestnet.py", line 442, in network_deploy
    node_group_cfg.regions,
  File "./tmtestnet.py", line 1100, in terraform_deploy_tendermint_node_group
    output_vars = load_yaml_config(output_vars_file)
  File "./tmtestnet.py", line 1737, in load_yaml_config
```

- quick fix: manually adjust the `output-vars.yaml` file by moving the `node` entries to be on new lines

### NOTE: Ignore Prior errors & warning: most likely due to Amazon account being in a 'pending' status in various regions
