"""
Simulateur Monte Carlo d'attaque par éclipse sur wallet SPV.
Mesure le taux d'occupation progressive des slots par l'attaquant
au fil des événements de reconnexion (issus des stats NS-3), ainsi
que la probabilité d'éclipse totale (les 8 slots contrôlés).
"""

import csv
import random
from pathlib import Path

K_SLOTS = 8
N_HONEST = 50
R_VALUES = [2, 4, 6]
N_TRIALS = 5000

SCENARIOS = {
    "wired": "results/raw/mobility_stats_wired.csv",
    "moderate": "results/raw/mobility_stats_moderate.csv",
    "high": "results/raw/mobility_stats_high.csv",
    "degraded": "results/raw/mobility_stats_degraded.csv",
}

RESULTS_DIR = Path("results/raw")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def count_reconnection_events(csv_path):
    with open(csv_path) as f:
        return len(list(csv.DictReader(f)))


def simulate_trial(r, n_honest, k_slots, n_events):
    """
    À chaque événement de reconnexion, TOUS les slots sont renégociés :
    chaque slot a une probabilité r/(r+n_honest) d'être pris par
    l'attaquant. On suit :
      - le pic d'occupation atteint (peak_occupancy)
      - si une éclipse totale (8/8) s'est produite au moins une fois
    """
    p_attacker = r / (r + n_honest)
    peak_occupancy = 0.0
    full_eclipse = False

    for _ in range(n_events):
        attacker_slots = sum(1 for _ in range(k_slots) if random.random() < p_attacker)
        occupancy = attacker_slots / k_slots
        peak_occupancy = max(peak_occupancy, occupancy)
        if attacker_slots == k_slots:
            full_eclipse = True

    return peak_occupancy, full_eclipse


def run_monte_carlo(r, n_honest, k_slots, n_events, n_trials):
    total_peak = 0.0
    eclipse_count = 0
    for _ in range(n_trials):
        peak, eclipsed = simulate_trial(r, n_honest, k_slots, n_events)
        total_peak += peak
        eclipse_count += eclipsed
    avg_peak_occupancy = total_peak / n_trials
    eclipse_rate = eclipse_count / n_trials
    return avg_peak_occupancy, eclipse_rate


def main():
    summary_rows = []

    for scenario_name, csv_path in SCENARIOS.items():
        path = Path(csv_path)
        if not path.exists():
            print(f"⚠️  Fichier manquant, ignoré : {csv_path}")
            continue

        n_events = max(1, count_reconnection_events(path))

        for r in R_VALUES:
            avg_occupancy, eclipse_rate = run_monte_carlo(
                r=r, n_honest=N_HONEST, k_slots=K_SLOTS,
                n_events=n_events, n_trials=N_TRIALS,
            )
            summary_rows.append({
                "scenario": scenario_name,
                "r_attackers": r,
                "n_honest": N_HONEST,
                "reconnection_events": n_events,
                "avg_peak_occupancy_rate": round(avg_occupancy, 4),
                "full_eclipse_probability": round(eclipse_rate, 4),
            })
            print(f"[{scenario_name:9s}] r={r} | événements={n_events:3d} "
                  f"| occupation pic moy. = {avg_occupancy:.1%} "
                  f"| P(éclipse totale) = {eclipse_rate:.2%}")

    if not summary_rows:
        print("❌ Aucun résultat — vérifie les chemins des CSV")
        return

    out_path = RESULTS_DIR / "eclipse_simulation_summary.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"\n✅ Résultats sauvegardés dans {out_path}")


if __name__ == "__main__":
    main()
