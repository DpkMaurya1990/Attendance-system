import pandas as pd
import matplotlib.pyplot as plt
import os


def generate_summary(records):
    df = pd.DataFrame(records)

    summary = df.groupby("status").size().reset_index(name="count")
    return summary


def save_attendance_to_csv(records):
    df = pd.DataFrame(records)
    file_path = "attendance_report.csv"
    df.to_csv(file_path, index=False)
    return file_path


def plot_summary_chart(summary_df):
    file_path = "attendance_chart.png"

    plt.figure(figsize=(4, 3))  # smaller chart
    plt.bar(summary_df["status"], summary_df["count"])
    plt.xlabel("Status")
    plt.ylabel("Count")
    plt.title("Attendance Summary")

    plt.savefig(file_path)
    plt.close("all")

    return file_path
