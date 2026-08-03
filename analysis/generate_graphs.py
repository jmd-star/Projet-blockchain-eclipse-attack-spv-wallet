"""
Génère les graphiques comparatifs à partir des résultats de simulation.
"""

import csv
from pathlib import Path
from collections import defaultdict
import matplotlib.pyplot as plt

SUMMARY_CSV = Path("results/raw/eclipse_simulation_summary.csv")
GRAPHS_DIR = Path("results/graphs")
GRAPHS_DIR.mkdir(parents=True, exist_ok=True)

SCENARIO_ORDER = ["wired", "moderate", "degraded", "high"]
SCENARIO_LABELS = {
    "wired": "Filaire\n(référence)",
    "moderate": "Mobilité\nmodérée",
    "degraded": "Signal\ndégradé",
    "high": "Mobilité\nélevée",
}
COLORS = {"wired": "#4C72B0", "moderate": "#DD8452", "degraded": "#C44E52", "high": "#55A868"}


def load_data():
    data = defaultdict(dict)  # data[scenario][r] = occupancy
    events = {}
    with open(SUMMARY_CSV) as f:
        for row in csv.DictReader(f):
            scenario = row["scenario"]
            r = int(row["r_attackers"])
            data[scenario][r] = float(row["avg_peak_occupancy_rate"])
            events[scenario] = int(row["reconnection_events"])
    return data, events


def plot_occupancy_by_scenario(data, r_fixed=6):
    """Graphique 1 : occupation pic (r=6) comparée entre les 4 scénarios."""
    scenarios = [s for s in SCENARIO_ORDER if s in data]
    values = [data[s][r_fixed] * 100 for s in scenarios]
    colors = [COLORS[s] for s in scenarios]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar([SCENARIO_LABELS[s] for s in scenarios], values, color=colors)
    ax.set_ylabel("Taux d'occupation adverse des slots (%)")
    ax.set_title(f"Occupation adverse maximale par scénario réseau (r={r_fixed} attaquants)")
    ax.set_ylim(0, max(values) * 1.3)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.5, f"{val:.1f}%",
                ha="center", fontweight="bold")
    plt.tight_layout()
    plt.savefig(GRAPHS_DIR / "occupancy_by_scenario.png", dpi=150)
    plt.close()
    print("✅ occupancy_by_scenario.png")


def plot_occupancy_by_r(data):
    """Graphique 2 : évolution de l'occupation selon r, pour chaque scénario."""
    fig, ax = plt.subplots(figsize=(8, 5))
    r_values = sorted(next(iter(data.values())).keys())

    for scenario in SCENARIO_ORDER:
        if scenario not in data:
            continue
        y = [data[scenario][r] * 100 for r in r_values]
        ax.plot(r_values, y, marker="o", linewidth=2, label=SCENARIO_LABELS[scenario].replace("\n", " "),
                 color=COLORS[scenario])

    ax.set_xlabel("Nombre de nœuds attaquants (r)")
    ax.set_ylabel("Taux d'occupation adverse des slots (%)")
    ax.set_title("Évolution de l'occupation adverse selon les ressources de l'attaquant")
    ax.set_xticks(r_values)
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(GRAPHS_DIR / "occupancy_by_r.png", dpi=150)
    plt.close()
    print("✅ occupancy_by_r.png")


def plot_events_vs_scenario(events):
    """Graphique 3 : nombre d'événements de reconnexion par scénario (contexte réseau)."""
    scenarios = [s for s in SCENARIO_ORDER if s in events]
    values = [events[s] for s in scenarios]
    colors = [COLORS[s] for s in scenarios]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar([SCENARIO_LABELS[s] for s in scenarios], values, color=colors)
    ax.set_ylabel("Nombre de transitions d'état RRC (300s)")
    ax.set_title("Fréquence des événements de reconnexion par scénario (mesuré via NS-3/LTE)")
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.3, str(val),
                ha="center", fontweight="bold")
    plt.tight_layout()
    plt.savefig(GRAPHS_DIR / "reconnection_events_by_scenario.png", dpi=150)
    plt.close()
    print("✅ reconnection_events_by_scenario.png")


def main():
    if not SUMMARY_CSV.exists():
        print(f"❌ Fichier introuvable : {SUMMARY_CSV} — lance d'abord eclipse_simulator.py")
        return
    data, events = load_data()
    plot_occupancy_by_scenario(data)
    plot_occupancy_by_r(data)
    plot_events_vs_scenario(events)
    print(f"\n✅ Tous les graphiques sont dans {GRAPHS_DIR}/")


if __name__ == "__main__":
    main()
