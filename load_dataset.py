import argparse
import pandas as pd
from API.gitlab_api_src import gitlab_flow

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument('--input_file_path', type=str)
    parser.add_argument('--token', type=str)
    parser.add_argument('--host', type=str, default='http://localhost')

    args = parser.parse_args()

    # Instanciate our library wrapper class
    gf = gitlab_flow(host=args.host, token=args.token)

    # Read the whole dataset and filter relevant columns
    ds = pd.read_csv(args.input_file_path)
    ds['source'] = ds['source'].apply(lambda x: x[3:])
    ds['target'] = ds['target'].apply(lambda x: x[3:])
    ds

    gf.flow(ds)

if __name__ == '__main__':
    main()