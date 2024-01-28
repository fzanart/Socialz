from datetime import timedelta
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
from scipy.stats import qmc
import graph_tool.all as gt
from scipy.stats import spearmanr


class ConvergencePlot:
    def draw(self, path):
        with open(path, encoding="utf-8") as f:
            text_file = f.readlines()[1:]

        text_file = [line.rstrip() for line in text_file]
        text_file = [line.split(", ") for line in text_file]

        score = []
        sample_size = []

        for line in text_file:
            txt, scr = line[1].split(": ")
            score.append(scr)
            txt, sz = line[2].split("}")[0].split(": ")
            sample_size.append(sz)

        score = [float(s) for s in score]
        sample_size = [int(s) for s in sample_size]
        df = pd.DataFrame({"score": score, "sample_size": sample_size})

        fig, ax1 = plt.subplots(figsize=(12, 5.6))
        ax2 = ax1.twinx()

        ax1.plot(df.index, df.sample_size, label="Mutations", color="dimgray")
        ax1.set_yscale("log")
        ax1.yaxis.set_major_formatter(ticker.ScalarFormatter())
        ax1.ticklabel_format(style="plain")
        ax1.minorticks_off()
        # ax1.set_title('Success-based multiplicative update rule \n', fontsize=22)
        ax1.set_ylabel("Mutations", fontsize=20)
        ax1.set_xlabel("Iterations", fontsize=20)
        ax1.yaxis.set_tick_params(labelsize=16)
        ax1.xaxis.set_tick_params(labelsize=16)

        ax2.plot(df.index, df.score, label="Star-discrepancy", color="brown")
        ax2.set_yscale("log")
        ax2.get_yaxis().set_major_formatter(ticker.ScalarFormatter())
        ax2.yaxis.set_major_locator(ticker.FixedLocator([0.06, 0.1, 0.3]))
        ax2.minorticks_off()
        ax2.ticklabel_format(style="plain")
        ax2.set_ylabel("Star-discrepancy", fontsize=20)
        ax2.yaxis.set_tick_params(labelsize=16)

        fig.legend(
            loc="upper right",
            bbox_to_anchor=(1, 1),
            bbox_transform=ax1.transAxes,
            fontsize=20,
        )

        return fig


class BenchmarkPlot:
    # get combinations!
    def __init__(self):
        self.COLOR_MAP = {
            "original": {"color": "brown", "edgecolor": "maroon", "marker": "^"},
            "evolved": {"color": "yellowgreen", "edgecolor": "olive", "marker": "H"},
            "simple": {"color": "violet", "edgecolor": "thistle", "marker": "X"},
            "random": {
                "color": "lightsteelblue",
                "edgecolor": "slategrey",
                "marker": "D",
            },
        }
        self.COLUMN_KEY_MAP = {
            "degree": "Degree centrality",
            "pagerank": "PageRank",
            "Values": "Event type",
        }

    # color, edgecolor, marker = 'brown','maroon','^' # original
    # color, edgecolor, marker = 'yellowgreen','olive','H' # evolved
    # color, edgecolor, marker = 'violet','thistle','X' # simple
    # color, edgecolor, marker = 'lightsteelblue','slategrey','D' # random

    def evaluation(self, dataset):
        # evaluate
        return qmc.discrepancy(dataset, method="L2-star", workers=-1)

    # plot:
    def draw_3d_plot(
        self, ax, data, dataset_name, title=False, alt_title=None
    ):  # , suptitle, size, long_title=True
        color_map = self.COLOR_MAP.get(dataset_name)
        edgecolor = color_map.get("edgecolor")
        color = color_map.get("color")
        marker = color_map.get("marker")

        ax.scatter3D(
            data["degree"],
            data["pagerank"],
            data["Values"],
            edgecolor=edgecolor,
            c=color,
            marker=marker,
        )
        ax.set_xlabel(self.COLUMN_KEY_MAP.get("degree"), fontsize=20, labelpad=-10)
        ax.set_ylabel(self.COLUMN_KEY_MAP.get("pagerank"), fontsize=20, labelpad=-10)
        ax.set_zlabel(self.COLUMN_KEY_MAP.get("Values"), fontsize=20, labelpad=-10)

        ax.set_xlim([0, 1])
        ax.set_ylim([0, 1])
        ax.set_zlim([0, 1])
        for axis in [ax.xaxis, ax.yaxis, ax.zaxis]:
            axis.set_ticklabels([])

        ax.xaxis._axinfo["grid"].update({"linewidth": 0.5, "color": "white"})
        ax.yaxis._axinfo["grid"].update({"linewidth": 0.5, "color": "white"})
        ax.zaxis._axinfo["grid"].update({"linewidth": 0.5, "color": "white"})

        if title:
            title_text = f"Star-discrepancy score: {self.evaluation(data):.3f}"
            if alt_title:
                title_text = alt_title

            ax.set_title(title_text, y=-0.2, fontsize=12)

        return ax

    def draw_2d_plot(self, ax, data, x, y, dataset_name):
        xlabel = self.COLUMN_KEY_MAP.get(x)
        ylabel = self.COLUMN_KEY_MAP.get(y)

        color_map = self.COLOR_MAP.get(dataset_name)
        edgecolor = color_map.get("edgecolor")
        color = color_map.get("color")
        marker = color_map.get("marker")

        ax.scatter(data[x], data[y], edgecolor=edgecolor, c=color, marker=marker)
        ax.set_xlabel(xlabel, fontsize=22, labelpad=-10)
        ax.set_ylabel(ylabel, fontsize=22, labelpad=-15)
        ax.tick_params(axis="x", colors="white")
        ax.tick_params(axis="y", colors="white")

        return ax


class NetworksPlot:
    def __init__(self) -> None:
        pass

    def draw_network(self, edgelist, output):
        g = gt.Graph(directed=True)
        vertices = g.add_edge_list(
            edgelist[["source", "target"]].to_numpy(), hashed=True
        )
        pos = gt.sfdp_layout(g)
        pr = gt.pagerank(g)
        degree = g.degree_property_map("total")
        gt.graph_draw(
            g,
            pos=pos,
            vertex_fill_color=pr,
            vertex_size=gt.prop_to_size(degree, mi=5, ma=15),
            vorder=pr,
            vcmap=plt.cm.summer,
            output=output,
        )


class GrafanaPlots:
    def __init__(self):
        self.COLOR_MAP = {
            "Simple": "thistle",
            "Random": "slategrey",
            "Original": "maroon",
            "Evolved": "olive",
        }

    def range_data(self, df, init_time, end_time, delta):
        df["Time"] = pd.to_datetime(df["Time"], utc=True)
        it = pd.to_datetime(init_time) + timedelta(minutes=delta)
        et = pd.to_datetime(end_time) + timedelta(minutes=delta)

        return df[(df["Time"] >= it) & (df["Time"] <= et)]

    def plot_lines(
        self, data, title, column, ylabel, xlabel, percentage=True, round_dec=0
    ):
        fig, ax = plt.subplots(figsize=(5, 5))

        for dataset in data:
            dataset = dataset.reset_index(drop=True)
            ax.plot(
                dataset.index,
                dataset[column],
                label=dataset.attrs["name"],
                color=self.COLOR_MAP.get(dataset.attrs["name"]),
            )
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), fancybox=True, ncol=4)
        ax.set_title(title, fontsize=18)
        ax.set_xlabel(xlabel, fontsize=16)
        ax.set_ylabel(ylabel, fontsize=16)
        ax.tick_params(axis="both", labelsize=14)
        if percentage:
            yticks = ax.get_yticks()
            if round_dec == 0:
                yticks = [int(round(100 * tick, round_dec)) for tick in yticks]
            else:
                yticks = [round(100 * tick, round_dec) for tick in yticks]
            ax.set_yticklabels(yticks)

        return fig


class CorrelationPlot:
    def __init__(self):
        self.COLOR_MAP = {
            "original": {"color": "brown", "edgecolor": "maroon", "marker": "^"},
            "evolved": {"color": "yellowgreen", "edgecolor": "olive", "marker": "H"},
            "simple": {"color": "violet", "edgecolor": "thistle", "marker": "X"},
            "random": {
                "color": "lightsteelblue",
                "edgecolor": "slategrey",
                "marker": "D",
            },
        }
        self.AXLABEL_MAP = {
            "CPU saturation": "CPU saturation (%)",
            "Memory saturation": "Memory saturation (%)",
            "Latency": "Latency (ms)",
        }

    def plot_correlation(self, data):
        fig, axs = plt.subplots(3, 3, figsize=(20, 20))

        for row, feature in enumerate(["PageRank", "Degree Centrality", "Event type"]):
            for column, metric in enumerate(
                ["CPU saturation", "Memory saturation", "Latency"]
            ):
                for dataset in data:
                    res = spearmanr(dataset[metric], dataset[feature])
                    dataset.plot(
                        kind="scatter",
                        x=feature,
                        y=metric,
                        marker=self.COLOR_MAP.get(dataset.attrs["name"]).get("marker"),
                        color=self.COLOR_MAP.get(dataset.attrs["name"]).get("color"),
                        edgecolor=self.COLOR_MAP.get(dataset.attrs["name"]).get(
                            "edgecolor"
                        ),
                        label=f'{dataset.attrs["name"][:3]} r({len(dataset)-2}) ={res.correlation:.2f}, p = {res.pvalue:.3f}',
                        ax=axs[row, column],
                    )

                    axs[row, column].set_ylabel(
                        self.AXLABEL_MAP.get(metric), fontsize=18
                    )
                    axs[row, column].set_xlabel(feature, fontsize=18)
                    axs[row, column].tick_params(axis="both", labelsize=16)
                    axs[row, column].set_title(f"{metric} vs {feature}", fontsize=20)
                    axs[row, column].legend(
                        loc="upper center",
                        bbox_to_anchor=(0.5, -0.15),
                        fancybox=True,
                        ncol=2,
                    )

                    yticks = axs[row, column].get_yticks()
                    yticks = [int(round(100 * tick, 0)) for tick in yticks]
                    axs[row, column].set_yticklabels(yticks)

        fig.suptitle(
            f"Correlation of user features and average resource utilisation.",
            fontsize=22,
            y=0.96,
        )
        fig.tight_layout(pad=5.0)

        return fig
