import collections
import json
import operator
import os.path
import subprocess

from collections import defaultdict
from pathlib import Path
from typing import Tuple, List
from urllib.error import HTTPError
from Bio import Entrez
from Bio import GenBank, SeqIO


def get_taxonomy(seq_ids: List[str]) -> Tuple[dict, dict]:
    """
    Takes in list of sequence IDs and makes calls to NCBI database to gather family and genus information for each ID.

    :param seq_ids: list of sequence IDs
    :return: family and genus dictionaries containing occurrences of each
    
    """
    families = defaultdict(int)
    genera = defaultdict(int)

    for seq_id in seq_ids:
        try:
            handle = Entrez.efetch(db="protein", id=seq_id, rettype="gb", retmode="text")
            for record in GenBank.parse(handle):

                family = record.taxonomy[-2]
                if family.lower() == "viruses":
                    family = "None"

                families[family] += 1

                genus = record.taxonomy[-1]
                if genus.lower() == "unclassified viruses":
                    genus = "None"

                genera[genus] += 1

        except (HTTPError, AttributeError):
            continue

    return dict(families), dict(genera)


def parse_log(cluster_name: str, output: Path) -> dict:
    """
    Parses log files and gathers count, alen, length, eff_nseqs, mean entropy and total_entropy.

    :param cluster_name: cluster name from which to gather log file
    :param output: path to output folder where .log files are stored
    :return: log_data, dictionary containing log_data
    """
    log_path = output / "intermediate_files" / Path(f"{cluster_name}.log")

    with log_path.open("r") as handle:
        for line in handle:
            line_data = line.strip().split()

            if line_data and "#" not in line_data[0]:
                count = float(line_data[2])
                mean_entropy = float(line_data[6])

                log_data = {
                    "count": count,
                    "alen": int(line_data[3]),
                    "length": int(line_data[4]),
                    "eff_nseq": float(line_data[5]),
                    "mean_entropy": mean_entropy,
                    "total_entropy": round(mean_entropy * count, 2)
                }

                return log_data

    return dict()


def parse_stat(cluster_name: str, output: Path) -> Tuple[float, float]:
    """
    Calls hmmstat and captures kullback_leibler_divergence and mean_positional_relative_entropy data.

    :param cluster_name: name of cluster file
    :param output: path to output directory
    :return: mean_positional_relative_entropy and kullback_leibler_divergence values
    """
    hmm_path = output / "intermediate_files" / f"{cluster_name}.hmm"

    hmmstat_cmd = ["hmmstat", hmm_path]
    stat_data = str(subprocess.run(hmmstat_cmd, capture_output=True)).split("\\n")

    for line in stat_data:
        if not line.startswith("#") and not line.startswith("CompletedProcess"):

            line = line.strip().split()
            mean_positional_relative_entropy = float(line[-2])
            kullback_leibler_divergence = float(line[-1])

            return mean_positional_relative_entropy, kullback_leibler_divergence

    raise Exception("hmmstat output not captured")


def get_names(annotation: dict) -> List[str]:
    """
    Returns three most common names in "entries" list and returns them to be output in json file.

    :param annotation: dictionary containing all information to be output to json file for one cluster
    :return: top three names
    """
    names = [entry["name"] for entry in annotation["entries"]]
    top_three = collections.Counter(names).most_common(3)

    return [entry[0] for entry in top_three]


def get_json_from_clusters(cluster_paths: List[Path], output: Path):
    """
    Parses all filtered FASTA cluster files and creates annotation dictionaries.

    All data from each annotation is written to master.json file.

    :param cluster_paths: list of paths to clustered, filtered FASTA files from vfam pipeline
    :param output: Path to output directory containing intermediate files from vfam pipeline
    """
    output_path = output / "master.json"
    annotations = list()

    for cluster_path in cluster_paths:
        annotation = {
            "cluster": os.path.basename(cluster_path).split("_")[1],
            "names": list(),
            "entries": list()
        }

        log_data = parse_log(os.path.basename(cluster_path), output)
        for key in log_data:
            annotation[key] = log_data[key]

        stat_data = parse_stat(os.path.basename(cluster_path), output)
        annotation["mean_positional_relative_entropy"] = stat_data[0]
        annotation["kullback_leibler_divergence"] = stat_data[1]

        with cluster_path.open("r") as handle:
            seq_ids = []
            for record in SeqIO.parse(handle, "fasta"):
                seq_ids.append(record.id)
                name = record.description.split("[")[0].split()
                name = " ".join(name[1:])

                annotation["entries"].append({
                    "accession": record.id,
                    "name": name,
                    "organism": record.description.split("[")[1].replace("]", "").strip()
                })

            taxonomy = get_taxonomy(seq_ids)
            if taxonomy:
                annotation["families"] = json.loads(str(taxonomy[0]).replace("'", '"'))
                annotation["genera"] = json.loads(str(taxonomy[1]).replace("'", '"'))

        annotation["names"] = get_names(annotation)
        annotation["entries"] = sorted(annotation["entries"], key=operator.itemgetter("accession"))

        annotations.append(annotation)

    annotations = sorted(annotations, key=operator.itemgetter("cluster"))

    with open(output_path, "wt") as f:
        json.dump(annotations, f, indent=4)
