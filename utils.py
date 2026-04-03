import pandas as pd
import matplotlib.pyplot as plt
import os


def generate_summary(records, column_name=None):
    df = pd.DataFrame(records)

    if column_name is None:
        column_name = "Status" if "Status" in df.columns else "status"

    if column_name not in df.columns:
        return pd.DataFrame(columns=[column_name, "count"])

    df = df[df[column_name].notna()]

    if column_name == "Event Status":
        df = df[df[column_name] != "N/A"]

    if df.empty:
        return pd.DataFrame(columns=[column_name, "count"])

    summary = df.groupby(column_name).size().reset_index(name="count")
    return summary


def save_attendance_to_csv(records):
    df = pd.DataFrame(records)
    file_path = "attendance_report.csv"
    df.to_csv(file_path, index=False)
    return file_path


def plot_summary_chart(summary_df, label_column=None, file_path="attendance_chart.png"):
    if label_column is None:
        if "Status" in summary_df.columns:
            label_column = "Status"
        elif "Event Status" in summary_df.columns:
            label_column = "Event Status"
        else:
            label_column = "status"

    plt.figure(figsize=(5, 4))
    plt.bar(summary_df[label_column], summary_df["count"])
    plt.xlabel(label_column)
    plt.ylabel("Count")
    plt.title(f"{label_column} Summary")
    plt.tight_layout()

    plt.savefig(file_path, bbox_inches="tight")
    plt.close("all")

    return file_path
