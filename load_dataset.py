import argparse
import pandas as pd
import matplotlib.pyplot as plt
from API.gitlabAPI import GitlabAPI
from Results import SuccessRate, PrometheusResuts


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--input_file_path", type=str)
    parser.add_argument("--output_path", type=str)  # /home/ubuntu/ or /mnt/?

    args = parser.parse_args()

    # Instanciate our library wrapper class
    api = GitlabAPI()
    edge_list = pd.read_csv(args.input_file_path)  # '/home/ubuntu/evo1.csv'
    api.flow(edge_list)

    # Save sucess rate from log file:
    sr = SuccessRate()
    log_file = sr.read(path=args.output_path + "load_dataset_logfile.log")
    sr_data = sr.relevant_data_to_df(log_file)
    sr_data.to_csv(args.output_path + "success_rate.csv", index=False)

    # Retrieve metrics from Prometheus:
    pr = PrometheusResuts()

    log_file = pr.read(logfile_path=args.output_path + "load_dataset_logfile.log")
    times = pr.time_delta(pr.start_finish_times(log_file))
    times = edge_list.join(times)
    times.to_csv(args.output_path + "event_times.csv", index=False)

    pr.global_metrics(args.output_path + "event_times.csv", args.output_path)
    pr.query_db(
        args.output_path + "event_times.csv", args.output_path + "event_metrics.csv"
    )


if __name__ == "__main__":
    main()
