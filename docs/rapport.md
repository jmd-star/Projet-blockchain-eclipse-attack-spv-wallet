# Simulation d'une attaque par éclipse sur wallet SPV en environnement mobile 3G/4G

**Projet final — Blockchain**
Master 1 RIST — Université Félix Houphouët-Boigny (UFHB)

---

## 1. Contexte et hypothèse 

Ce projet étudie la vulnérabilité des **wallets SPV** (Simplified Payment Verification) face à l'**attaque par éclipse** — une attaque où un adversaire monopolise l'ensemble des connexions pair-à-pair (P2P) d'une victime pour l'isoler du réseau blockchain légitime dans le contexte spécifique d'un **réseau mobile 3G/4G**, où mobilité, handovers et dégradation de signal créent des fenêtres de vulnérabilité récurrentes.

L'hypothèse centrale testée : **les contraintes du réseau mobile (mobilité, qualité de signal) augmentent la surface d'exposition du wallet à une prise de contrôle adverse de ses slots de connexion**, comparativement à un réseau filaire stable.

## 2. Architecture de simulation

La simulation repose sur une architecture à deux couches, développée séparément pour des raisons de faisabilité dans le délai imparti :

### Couche réseau mobile (NS-3 / module LTE-LENA)
Un environnement NS-3 simule un UE (User Equipment, représentant le wallet) se déplaçant entre deux eNodeB LTE, avec un algorithme de handover A3-RSRP (hystérésis 3 dB, temps de déclenchement 256 ms valeurs standards de la littérature LTE). Chaque transition d'état RRC (`LteUeRrc::StateTransition`) est tracée et horodatée, servant d'indicateur des fenêtres de reconnexion/vulnérabilité.

### Couche blockchain (simulateur Python, Monte Carlo)
Un modèle Monte Carlo simule le comportement du wallet SPV lors de chaque événement de reconnexion détecté par la couche réseau : à chaque reconnexion, les **K = 8 slots** du wallet sont renégociés parmi un pool de pairs composé de **N = 50 pairs honnêtes** et **r nœuds attaquants** (r ∈ {2, 4, 6}), chaque slot ayant une probabilité `r / (r + N)` d'être capturé par l'attaquant.

Ce découplage permet d'isoler l'effet des conditions réseau sur la surface d'exposition, sans nécessiter une intégration temps réel complexe entre les deux simulateurs — un compromis raisonnable compte tenu du délai du projet.

## 3. Scénarios testés

| Scénario | Configuration NS-3 | Événements de reconnexion (300s) |
|---|---|---|
| Filaire (référence) | UE statique, aucune mobilité | 5 |
| Mobilité modérée | Vitesse piéton (1,3 m/s / <5 km/h) | 11 |
| Signal dégradé | UE statique, puissance eNodeB réduite (20 dBm au lieu de 46 dBm) | 11 |
| Mobilité élevée | Vitesse véhicule (10 m/s / 36 km/h) | 25 |

## 4. Résultats

### 4.1 Fréquence des reconnexions
La mobilité élevée génère **5x plus d'événements de reconnexion** que le scénario filaire (25 contre 5), confirmant que le déplacement rapide entre cellules LTE multiplie les fenêtres où le wallet doit renégocier ses connexions P2P.

### 4.2 Taux d'occupation adverse des slots (métrique principale)

| Scénario | r=2 | r=4 | r=6 |
|---|---|---|---|
| Filaire | 12,3% | 18,8% | 24,0% |
| Mobilité modérée | 16,6% | 24,1% | 30,2% |
| Signal dégradé | 16,7% | 24,1% | 29,9% |
| **Mobilité élevée** | **21,0%** | **29,4%** | **35,7%** |

Deux tendances se dégagent clairement :
1. **Effet des ressources de l'attaquant** : le taux d'occupation croît avec r dans tous les scénarios (comportement attendu, cohérent avec la proportion `r/(r+N)`).
2. **Effet des conditions réseau** : à r fixé, la mobilité élevée expose le wallet à un taux d'occupation adverse **jusqu'à +49% supérieur** au scénario filaire (35,7% vs 24,0% pour r=6). Le signal dégradé et la mobilité modérée ont un effet comparable et intermédiaire (+24 à +26%).

### 4.3 Probabilité d'éclipse totale
Sur les combinaisons testées (r ≤ 6, N = 50, événements ≤ 25), la probabilité d'observer une éclipse **complète** (8/8 slots) par pur hasard reste proche de 0%. Ce résultat est cohérent avec la littérature : les attaques éclipse réelles ne reposent pas sur le hasard seul, mais combinent la fenêtre de vulnérabilité (mise en évidence ici) avec des techniques de manipulation d'adressage IP (multiples adresses par attaquant, contournement des règles anti-Sybil du protocole P2P) pour garantir la capture des slots plutôt que de l'espérer statistiquement.

## 5. Recommandations pour sécuriser les wallets mobiles

1. **Diversification renforcée des pairs** : privilégier une sélection de pairs par plages d'adresses IP distinctes (anti-Sybil), particulièrement critique en contexte mobile où les reconnexions sont fréquentes.
2. **Détection précoce par surveillance du délai de propagation** : un délai anormal de réception de nouveaux blocs après une reconnexion peut signaler une tentative d'éclipse en cours.
3. **Persistance de pairs de confiance** : conserver en mémoire un sous-ensemble de pairs historiquement fiables à re-solliciter en priorité lors d'une reconnexion, plutôt qu'un remplissage aléatoire complet des 8 slots.
4. **Délai de confirmation adaptatif** : dans les zones à forte mobilité ou signal dégradé (scénarios les plus exposés selon nos résultats), augmenter le nombre de confirmations requises avant d'accepter une transaction, le temps que la connectivité se stabilise.

## 6. Limites de l'étude

- Le couplage entre les deux couches (réseau et blockchain) est **statistique et non temps réel** : les métriques réseau (NS-3) alimentent le modèle Monte Carlo en post-traitement plutôt qu'en interaction dynamique complète.
- Le modèle analytique formalisé (chaîne de Markov à 5 états) n'a pas été démontré mathématiquement dans le cadre de ce projet, conformément aux consignes.
- La question de l'impact précis de la mobilité sur la probabilité de monopolisation n'a pas été traitée en détail analytique, conformément aux consignes.

## 7. Conclusion

Cette étude confirme l'hypothèse centrale : les contraintes des réseaux mobiles 3G/4G en particulier la mobilité élevée  augmentent significativement l'exposition des wallets SPV à une prise de contrôle partielle de leurs connexions P2P, comparativement à un environnement filaire stable. Si l'éclipse totale par pur hasard reste rare sur les échelles testées, le taux d'occupation adverse croissant constitue un indicateur d'alerte exploitable pour la détection précoce, et souligne l'intérêt de mécanismes de sélection de pairs plus robustes dans les wallets mobiles.
