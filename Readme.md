# Socialz: Multi-Feature Social Fuzz Testing

> Abstract:   
Online social networks have become an integral aspect of our daily lives and play a crucial role in shaping our relationships with others. However, bugs and glitches, even minor ones, can cause anything from frustrating problems to serious data leaks that can have far-reaching impacts on millions of users. To mitigate these risks, fuzz testing, a method of testing with randomised inputs, can provide increased confidence in the correct functioning of a social network. However, implementing traditional fuzz testing methods can be prohibitively difficult or impractical for programmers outside of the network's development team. To tackle this challenge, we present Socialz, a novel approach to social fuzz testing that (1) characterises real users of a social network, (2) diversifies their interaction using evolutionary computation across multiple, non-trivial features, and (3) collects performance data as these interactions are executed. With Socialz, we aim to provide anyone with the capability to perform comprehensive social testing, thereby improving the reliability and security of online social networks used around the world. 

> Authors:   
Francisco Zanartu, Christoph Treude, Markus Wagner  

> Paper:   
https://arxiv.org/abs/2302.08664

This repository contains:
- Relevant codes of our work   
- Datasets
- Usage instructions
- Setup instructions

# evolution_run.py:

### Input 

To optimise a .csv dataset we start with one on the form:

| source | target | type |

Note: In our case, we assumed no user-user connections (i.e. type == 'FollowEvent') in our original dataset, intead we create Follow Events by calculating cosine similarity between users. We assumed only users in the 'source' column and only repositories in the 'target' column. We also added a leading character 'r: ' for repository and 'u: ' for user.

### Output

This script outputs a .csv file with the evolved dataset in `/Datasets/` directory.

### Usage

`python evolution_run.py --input_file_path your_file_path --output_filename your_file_name`

Additional parameters:   
`multiprocessing_units` enables multiprocessing.  Set a value for the number of cores in your machine.   
`n_iter` Set the number of iterations for the evolutionary algorithm, default = `1000`.  
`mu` The number of parents selected each iteration, default = `1`.   
`lam` Size of the population, default = `20`.   
`A`  Mutation rate increase factor, default = `2`.   
`b`  Mutation rate decrease factor, default = `0.5`.   
`disable_progress_bar` Set to True if you want to disable the progress bar, default = `False`.

# load_dataset.py:

### Input

This program loads a .csv dataset into a Gitlab server, it starts by reading file and the removing the leading 'r: ', 'u: ' characters from evolution_run.py

### Usage

`python load_dataset.py --input_file_path your_file_path --token your_file_name your_token`

Additional parameters:   
`host` Set the host address, default = `http://localhost`
