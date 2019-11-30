Adi Seredinschi <adi@interchain.io> | 30 Nov. 2019

# Preparing to run testnet with optimal configuration

### 1. Optimal config from Thane

```
mempool.size = 50000
cleveldb
mempool.recheck = false
skip_timeout_commit = true
create_empty_blocks = false
```


### 2. Local compile the right tendermint version w/ cleveldb

Quote (from Thane):
```
So to build this version of the binary:
1. Clone the latest release of the Tendermint source code (git checkout v0.32.7)
2. make build_c-amazonlinux
The cleveldb-compatible Tendermint binary, built for Amazon Linux, will be in
your local build directory. Use the path to that Tendermint binary as part of
the tmtestnet configuration for all your nodes.
```

Did this on my local machine and then updated the `binary` property in nets.yaml
to point to the right binary from the build.

### 3. Choose the right AMI

* starting from AMI ID: ami-0d344de126a83ea6b
* had to install gcc-c++-7.3.1-6.amzn2.0.4.x86_64.rpm to be able to compile leveldb
* then compile leveldb: [as here](https://github.com/tendermint/tendermint/blob/6a4608230cd4a584490d01b2775c18f3b80b38a2/docs/introduction/install.md#compile-with-cleveldb-support)
* note that the dynamic linker needs the path to the libs: `ldconfig -v /usr/local/lib/`
* update `tendermint/terraform/main.tf` witht the correct AMI IDs


### 4. Deploy and start the network