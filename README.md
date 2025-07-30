# RF*diffusion*

This is the Kuhlman Lab fork of [RFdiffusion](https://github.com/RosettaCommons/RFdiffusion).

RFdiffusion is an open source method for structure generation, with or without conditional information (a motif, target etc). It can perform a whole range of protein design challenges as outlined in the [RFdiffusion paper](https://www.nature.com/articles/s41586-023-06415-8).

All of the functionality of the original repo is preserved (refer to the [original README](https://github.com/RosettaCommons/RFdiffusion?tab=readme-ov-file#description) for detailed explanations). A few additional changes have been made in this repo:
- Symmetry: Random chain lengths can now be used no matter what symmetry order.
- New potentials: 1) `loop_contacts` for biasing the distance between two residues, 2) `hetero_olig` for biasing number of inter- and intra-chain contacts, 3) `binder_RMSD` for biasing binder topologies towards a specific shape based on RMSD, 4) `res_pair_constraints` for biasing binder topologies towards a specific shape based on residue pair distances.
- Utilities for interacting with EvoPro.

## Installation

We provide an alternative installation process for RFdiffusion. 
1. Clone the repo: 
```
git clone https://github.com/Kuhlman-Lab/RFdiffusion.git
```
2. Download the model parameters:
``` 
cd RFdiffusion
mkdir models; cd models
wget http://files.ipd.uw.edu/pub/RFdiffusion/6f5902ac237024bdd0c176cb93063dc4/Base_ckpt.pt
wget http://files.ipd.uw.edu/pub/RFdiffusion/e29311f6f1bf1af907f9ef9f44b8328b/Complex_base_ckpt.pt
wget http://files.ipd.uw.edu/pub/RFdiffusion/60f09a193fb5e5ccdc4980417708dbab/Complex_Fold_base_ckpt.pt
wget http://files.ipd.uw.edu/pub/RFdiffusion/74f51cfb8b440f50d70878e05361d8f0/InpaintSeq_ckpt.pt
wget http://files.ipd.uw.edu/pub/RFdiffusion/76d00716416567174cdb7ca96e208296/InpaintSeq_Fold_ckpt.pt
wget http://files.ipd.uw.edu/pub/RFdiffusion/5532d2e1f3a4738decd58b19d633b3c3/ActiveSite_ckpt.pt
wget http://files.ipd.uw.edu/pub/RFdiffusion/12fc204edeae5b57713c5ad7dcb97d39/Base_epoch8_ckpt.pt
wget http://files.ipd.uw.edu/pub/RFdiffusion/f572d396fae9206628714fb2ce00f72e/Complex_beta_ckpt.pt
```
3. Create a new environment based on the yaml file (rfdiff_env.yaml):
```
cd ../env
conda env create -n rfdiff -f rfdiff_env.yaml
```
4. Activate the new environment:
```
conda activate rfdiff
```
5. Install dllogger:
```
pip install "dllogger @ git+https://github.com/NVIDIA/dllogger.git"
```
6. Install se3-transformer:
```
cd SE3Transformer
python setup.py install
```
7. Install rfdiffusion:
```
cd ../..
pip install -e .
```

**Note:** It should also be possible to follow the instructions in the original repo, but only difference is to clone this repo (`git clone https://github.com/Kuhlman-Lab/RFdiffusion.git`) rather than the original. 
