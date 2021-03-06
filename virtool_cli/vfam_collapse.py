import subprocess

from pathlib import Path
from Bio import SeqIO


def generate_clusters(curated_fasta_path: Path, fraction_id: float, prefix=None, fraction_cov=None) -> Path:
    """
    Takes in path to a FASTA file, minimum fraction ID, minimum fraction coverage and calls CD-HIT to cluster data.

    CD-HIT collapses the input sequences into non-redundant representatives at the specified levels.

    :param curated_fasta_path: path to FASTA file from vfam_curate step, to have cd-hit performed on it
    :param fraction_id: Fraction ID for cd-hit step
    :param prefix: Prefix for intermediate and result files
    :param fraction_cov: Fraction coverage for cd-hit step
    :return: output_path, path to a file containing cluster information created at cd-hit step
    """
    output_name = "clustered_fasta.faa"
    if prefix:
        output_name = f"{prefix}_{output_name}"

    output_path = curated_fasta_path.parent / output_name

    cd_hit_cmd = [
        "cd-hit",
        "-i", curated_fasta_path,
        "-o", output_path,
        "-s", str(fraction_id)
    ]

    if fraction_cov:
        cd_hit_cmd += ["-c", str(fraction_cov)]

    subprocess.run(cd_hit_cmd, check=True, shell=False)

    return output_path


def rmv_polyproteins(clustered_fasta_path: Path) -> list:
    """
    Parses through clustered_fasta_path file and yields records if "polyprotein" not found in record description.

    :param clustered_fasta_path: path to clustered FASTA file from generate_clusters()
    """
    for record in SeqIO.parse(clustered_fasta_path, "fasta"):
        if "polyprotein" not in record.description:
            yield record


def write_rmv_polyproteins(clustered_fasta_path: Path, prefix=None) -> Path:
    """
    Writes all records from rmw_polyproteins() step to output_path.

    :param clustered_fasta_path: path to file containing clustered FASTA information from generate clusters step
    :param prefix: Prefix for intermediate and result files
    :return: output_path, path to a file containing all clustered FASTA records with polyprotein_ids removed
    """
    output_name = "no_named_polyproteins.faa"

    if prefix:
        output_name = f"{prefix}_{output_name}"

    output_path = clustered_fasta_path.parent / Path(output_name)

    SeqIO.write(rmv_polyproteins(clustered_fasta_path), output_path, "fasta")

    return output_path


def blast_all_by_all(clustered_fasta_path: Path, num_cores: int, prefix=None) -> Path:
    """
    Takes a clustered FASTA file as input, and formats file to be a BLAST protein database.

    Runs BLAST on the file to itself as the BLAST-formatted database.

    :param clustered_fasta_path: path to FASTA file from previous cd-hit step
    :param num_cores: number of cores to use at all_by_all blast step
    :param prefix: Prefix for intermediate and result files
    :return: path to tab-delimited formatted BLAST results file
    """
    format_db_cmd = [
        "makeblastdb",
        "-in", clustered_fasta_path,
        "-dbtype", "prot"
    ]

    subprocess.run(format_db_cmd, check=True, shell=False)

    blast_name = "blast.br"
    if prefix:
        blast_name = f"{prefix}_{blast_name}"

    blast_results_path = clustered_fasta_path.parent / Path(blast_name)

    blast_cmd = [
        "blastp",
        "-query", clustered_fasta_path,
        "-out", blast_results_path,
        "-db", clustered_fasta_path,
        "-outfmt", "6",
        "-num_threads", str(num_cores)
    ]

    subprocess.run(blast_cmd, check=True, shell=False)

    return blast_results_path
