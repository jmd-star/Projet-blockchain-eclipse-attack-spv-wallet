# Guide technique complet Simulation d'attaque par éclipse sur wallet SPV (réseau mobile 3G/4G)

Projet final — Blockchain — M1 RIST — UFHB

**Environnement de référence :** WSL2, Ubuntu 26.04 LTS ("resolute"), Python 3.14 par défaut.

---

## Table des matières

1. [Préparation de l'environnement](#1-préparation-de-lenvironnement)
2. [Structure du projet](#2-structure-du-projet)
3. [Installation de NS-3](#3-installation-de-ns-3)
4. [Contournement du bug Python 3.14](#4-contournement-du-bug-python-314)
5. [Compilation de NS-3](#5-compilation-de-ns-3)
6. [Script NS-3 : extraction des stats de mobilité](#6-script-ns-3--extraction-des-stats-de-mobilité)
7. [Génération des 4 scénarios](#7-génération-des-4-scénarios)
8. [Simulateur Python Monte Carlo](#8-simulateur-python-monte-carlo)
9. [Génération des graphiques](#9-génération-des-graphiques)

---

## 1. Préparation de l'environnement

Vérifier la version d'Ubuntu :

```bash
lsb_release -a
```

Installer les dépendances système nécessaires à NS-3 :

```bash
sudo apt update

sudo apt install -y \
    g++ cmake ninja-build git \
    python3 python3-dev python3-pip \
    ccache \
    libgtk-3-dev \
    libxml2-dev \
    libgsl-dev \
    libsqlite3-dev sqlite3 \
    gnuplot \
    tcpdump wireshark-common \
    doxygen graphviz
```

> **Note :** sur certaines versions récentes d'Ubuntu, le paquet `libxml2` seul n'a pas de candidat d'installation — `libxml2-dev` suffit (il l'inclut déjà). Si `wireshark-common` n'est pas trouvable, retirez-le de la liste ; il n'est pas critique.

---

## 2. Structure du projet

```bash
cd ~
mkdir -p eclipse-attack-reseau/{scratch,src/blockchain,scenarios,results/{raw,graphs},analysis,docs}
cd eclipse-attack-reseau
git init

cat > .gitignore << 'EOF'
# NS-3 (outil externe téléchargé — ne pas versionner)
ns-allinone-3.42/
ns-allinone-3.42.tar.bz2

# Build artifacts
build/
cmake-cache/
*.o
*.so
*.log
*.pcap

# Python
__pycache__/
*.pyc
venv/

# Divers
.vscode/
*.swp
EOF

cat > README.md << 'EOF'
# Simulation d'attaque par éclipse sur wallet SPV (réseau mobile 3G/4G)

Projet final - Blockchain et Technologies Distribuées - M1 RIST - UFHB

## Structure
- `scratch/` : script NS-3 principal (extraction stats mobilité)
- `analysis/` : simulateur Monte Carlo Python + génération de graphiques
- `results/raw/` : données brutes (CSV)
- `results/graphs/` : graphiques générés
- `docs/` : rapport final
EOF

```

> **Point important :** NS-3 doit être installé **à l'extérieur** de ce que vous versionnez, ou explicitement exclu via `.gitignore` comme ci-dessus (voir section 12 pour le nettoyage si vous avez oublié cette étape).

---

## 3. Installation de NS-3

```bash
cd ~/eclipse-attack-reseau
wget https://www.nsnam.org/releases/ns-allinone-3.42.tar.bz2
tar xjf ns-allinone-3.42.tar.bz2
ls   # doit montrer ns-allinone-3.42/
```

---

## 4. Contournement du bug Python 3.14

**Problème :** le script `ns3` fourni avec la version 3.42 utilise une syntaxe `argparse` (`action="store_true"` sur des arguments positionnels) que Python 3.14 rejette désormais strictement (`ValueError: action 'store_true' is not valid for positional arguments`). C'est un bug de compatibilité connu, corrigé uniquement dans les versions de développement de NS-3.

**Solution retenue : installer Python 3.12 via `pyenv`** (contourne le bug sans toucher au script NS-3).

```bash
# Dépendances de compilation Python
sudo apt install -y build-essential libssl-dev libbz2-dev \
    libreadline-dev libncursesw5-dev tk-dev libxml2-dev \
    libxmlsec1-dev liblzma-dev curl

# Installer pyenv
curl https://pyenv.run | bash

echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
source ~/.bashrc

# Compiler et installer Python 3.12 (prend 5-10 min)
pyenv install 3.12.8

# Vérifier
~/.pyenv/versions/3.12.8/bin/python3.12 --version
```

À partir de maintenant, **toute commande `./ns3` doit être appelée via cet interpréteur** :

```bash
PY=~/.pyenv/versions/3.12.8/bin/python3.12
$PY ./ns3 <commande>
```

---

## 5. Compilation de NS-3

```bash
cd ~/eclipse-attack-reseau/ns-allinone-3.42/ns-3.42
PY=~/.pyenv/versions/3.12.8/bin/python3.12

$PY ./ns3 configure --enable-examples --enable-tests
$PY ./ns3 build
```

**Vérification rapide :**

```bash
$PY ./ns3 run hello-simulator
$PY ./ns3 run lena-simple-epc
```

---

## 6. Script NS-3 : extraction des stats de mobilité

Ce script simule le wallet se déplaçant entre deux eNodeB LTE, avec un vrai algorithme de handover (A3-RSRP) et une zone de déplacement couvrant tout l'espace entre les deux antennes. Il enregistre chaque transition d'état RRC dans un CSV.

```bash
cd ~/eclipse-attack-reseau/ns-allinone-3.42/ns-3.42
cat > scratch/mobility-stats.cc << 'CPPEOF'
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/mobility-module.h"
#include "ns3/lte-module.h"
#include "ns3/internet-module.h"
#include "ns3/point-to-point-module.h"
#include <fstream>

using namespace ns3;

std::ofstream g_traceFile;

void
StateTransitionCallback(std::string context, uint64_t imsi, uint16_t cellId, uint16_t rnti,
                         LteUeRrc::State oldState, LteUeRrc::State newState)
{
    g_traceFile << Simulator::Now().GetSeconds() << ","
                << imsi << "," << oldState << "," << newState << std::endl;
}

int
main(int argc, char* argv[])
{
    double speed = 5.0;
    double simTime = 300.0;
    double txPower = 46.0;
    std::string scenario = "moderate";
    std::string outFile = "results/raw/mobility_stats_moderate.csv";

    CommandLine cmd;
    cmd.AddValue("speed", "UE speed in m/s", speed);
    cmd.AddValue("simTime", "Simulation duration in seconds", simTime);
    cmd.AddValue("txPower", "eNB transmit power in dBm (lower = weaker signal)", txPower);
    cmd.AddValue("scenario", "Scenario label", scenario);
    cmd.AddValue("outFile", "Output CSV path", outFile);
    cmd.Parse(argc, argv);

    g_traceFile.open(outFile);
    g_traceFile << "time,imsi,oldState,newState" << std::endl;

    Ptr<LteHelper> lteHelper = CreateObject<LteHelper>();
    Ptr<PointToPointEpcHelper> epcHelper = CreateObject<PointToPointEpcHelper>();
    lteHelper->SetEpcHelper(epcHelper);
    lteHelper->SetHandoverAlgorithmType("ns3::A3RsrpHandoverAlgorithm");
    lteHelper->SetHandoverAlgorithmAttribute("Hysteresis", DoubleValue(3.0));
    lteHelper->SetHandoverAlgorithmAttribute("TimeToTrigger", TimeValue(MilliSeconds(256)));

    Config::SetDefault("ns3::LteEnbPhy::TxPower", DoubleValue(txPower));

    NodeContainer enbNodes;
    enbNodes.Create(2);
    NodeContainer ueNodes;
    ueNodes.Create(1);

    MobilityHelper enbMobility;
    enbMobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    Ptr<ListPositionAllocator> enbPositions = CreateObject<ListPositionAllocator>();
    enbPositions->Add(Vector(0.0, 0.0, 0.0));
    enbPositions->Add(Vector(500.0, 0.0, 0.0));
    enbMobility.SetPositionAllocator(enbPositions);
    enbMobility.Install(enbNodes);

    MobilityHelper ueMobility;
    if (scenario == "wired" || speed == 0.0)
    {
        ueMobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
        Ptr<ListPositionAllocator> uePosAlloc = CreateObject<ListPositionAllocator>();
        uePosAlloc->Add(Vector(0.0, 10.0, 0.0));
        ueMobility.SetPositionAllocator(uePosAlloc);
    }
    else
    {
        Ptr<UniformRandomVariable> xVar = CreateObject<UniformRandomVariable>();
        xVar->SetAttribute("Min", DoubleValue(0.0));
        xVar->SetAttribute("Max", DoubleValue(500.0));

        Ptr<UniformRandomVariable> yVar = CreateObject<UniformRandomVariable>();
        yVar->SetAttribute("Min", DoubleValue(0.0));
        yVar->SetAttribute("Max", DoubleValue(20.0));

        Ptr<UniformRandomVariable> zVar = CreateObject<UniformRandomVariable>();
        zVar->SetAttribute("Min", DoubleValue(0.0));
        zVar->SetAttribute("Max", DoubleValue(0.0));

        Ptr<RandomBoxPositionAllocator> boxPosAlloc = CreateObject<RandomBoxPositionAllocator>();
        boxPosAlloc->SetAttribute("X", PointerValue(xVar));
        boxPosAlloc->SetAttribute("Y", PointerValue(yVar));
        boxPosAlloc->SetAttribute("Z", PointerValue(zVar));

        ueMobility.SetPositionAllocator(boxPosAlloc);
        ueMobility.SetMobilityModel(
            "ns3::RandomWaypointMobilityModel",
            "Speed", StringValue("ns3::ConstantRandomVariable[Constant=" + std::to_string(speed) + "]"),
            "Pause", StringValue("ns3::ConstantRandomVariable[Constant=0.0]"),
            "PositionAllocator", PointerValue(boxPosAlloc));
    }
    ueMobility.Install(ueNodes);

    NetDeviceContainer enbDevs = lteHelper->InstallEnbDevice(enbNodes);
    NetDeviceContainer ueDevs = lteHelper->InstallUeDevice(ueNodes);

    InternetStackHelper internet;
    internet.Install(ueNodes);
    epcHelper->AssignUeIpv4Address(NetDeviceContainer(ueDevs));

    lteHelper->Attach(ueDevs.Get(0), enbDevs.Get(0));
    lteHelper->AddX2Interface(enbNodes);

    Config::Connect("/NodeList/*/DeviceList/*/LteUeRrc/StateTransition",
                     MakeCallback(&StateTransitionCallback));

    Simulator::Stop(Seconds(simTime));
    Simulator::Run();
    Simulator::Destroy();

    g_traceFile.close();
    return 0;
}
CPPEOF

mkdir -p results/raw results/graphs
```

**Points de conception importants** (voir section 11 pour le détail des bugs évités) :
- L'allocateur de position (`RandomBoxPositionAllocator`) est construit **directement en C++** avec ses variables aléatoires X/Y/Z, plutôt que via une chaîne de caractères — plus robuste face aux erreurs de syntaxe d'attributs.
- L'algorithme de handover **A3-RSRP** est activé explicitement (NS-3 utilise `NoOpHandoverAlgorithm` par défaut, qui ne déclenche jamais de handover).
- La zone de mobilité couvre `X ∈ [0, 500]` — exactement l'espace entre les deux eNodeB — pour que l'UE traverse réellement la zone de handover.

---

## 7. Génération des 4 scénarios

```bash
cd ~/eclipse-attack-reseau/ns-allinone-3.42/ns-3.42
PY=~/.pyenv/versions/3.12.8/bin/python3.12

$PY ./ns3 build mobility-stats

# Filaire (référence — aucune mobilité)
$PY ./ns3 run "mobility-stats --scenario=wired --speed=0 --outFile=results/raw/mobility_stats_wired.csv"

# Mobilité modérée (piéton, <5 km/h)
$PY ./ns3 run "mobility-stats --scenario=moderate --speed=1.3 --outFile=results/raw/mobility_stats_moderate.csv"

# Mobilité élevée (véhicule, >30 km/h)
$PY ./ns3 run "mobility-stats --scenario=high --speed=10 --outFile=results/raw/mobility_stats_high.csv"

# Signal dégradé (zone rurale — puissance eNodeB réduite)
$PY ./ns3 run "mobility-stats --scenario=degraded --speed=1.3 --txPower=20 --outFile=results/raw/mobility_stats_degraded.csv"

wc -l results/raw/*.csv
```

**Résultats attendus** (nombre de lignes = nombre de transitions d'état RRC + 1 ligne d'en-tête) :

| Scénario | Lignes attendues |
|---|---|
| Filaire | ~6 |
| Modérée | ~12 |
| Dégradé | ~12 |
| Élevée | ~26 |

Copier ces fichiers vers le dossier de travail principal du projet (utilisé par le simulateur Python) :

```bash
cd ~/eclipse-attack-reseau
mkdir -p results/raw
cp ns-allinone-3.42/ns-3.42/results/raw/*.csv results/raw/
```

---

## 8. Simulateur Python Monte Carlo

Ce script utilise le nombre d'événements de reconnexion (issu de la section 7) comme paramètre d'entrée d'une simulation Monte Carlo du remplissage des slots du wallet.

```bash
cd ~/eclipse-attack-reseau
pip install matplotlib --break-system-packages

cat > analysis/eclipse_simulator.py << 'PYEOF'
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
PYEOF

python3 analysis/eclipse_simulator.py
```

**Paramètres du modèle :**
- `K_SLOTS = 8` : nombre de slots de connexion du wallet SPV (valeur typique Bitcoin)
- `N_HONEST = 50` : taille du pool de pairs honnêtes disponibles
- `R_VALUES = [2, 4, 6]` : nombre de nœuds attaquants testés
- Métrique principale : **taux d'occupation adverse des slots** (plutôt que la seule probabilité d'éclipse totale, trop rare statistiquement à cette échelle pour être discriminante entre scénarios)

**Résultats attendus** (occupation pic moyenne, r=6) : Filaire 24,0% · Modérée 30,2% · Dégradée 29,9% · Élevée 35,7%.

---

## 9. Génération des graphiques

```bash
cd ~/eclipse-attack-reseau
cat > analysis/generate_graphs.py << 'PYEOF'
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
    data = defaultdict(dict)
    events = {}
    with open(SUMMARY_CSV) as f:
        for row in csv.DictReader(f):
            scenario = row["scenario"]
            r = int(row["r_attackers"])
            data[scenario][r] = float(row["avg_peak_occupancy_rate"])
            events[scenario] = int(row["reconnection_events"])
    return data, events


def plot_occupancy_by_scenario(data, r_fixed=6):
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
PYEOF

python3 analysis/generate_graphs.py
ls results/graphs/
```

---

## Résumé des résultats finaux

| Scénario | Événements reco. (300s) | Occupation pic (r=6) |
|---|---|---|
| Filaire (référence) | 5 | 24,0% |
| Mobilité modérée | 11 | 30,2% |
| Signal dégradé | 11 | 29,9% |
| Mobilité élevée | 25 | 35,7% |

**Conclusion validée :** la mobilité élevée expose le wallet SPV à un taux d'occupation adverse jusqu'à **+49%** supérieur au scénario filaire, confirmant que les contraintes des réseaux mobiles 3G/4G aggravent la vulnérabilité à l'attaque par éclipse.
