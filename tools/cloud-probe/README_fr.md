# Sonde réseau pour l'API cloud BLUETTI dans Home Assistant

*English version: [README.md](README.md)*

> **Un outil de diagnostic temporaire, qui ne fait pas partie de l'intégration.** Il lit le jeton de l'intégration dans le stockage de Home Assistant et ajoute environ 6 à 8 requêtes par minute à un cloud déjà en difficulté. Lance-le pour documenter une panne, puis arrête-le (section 8).

Ce guide explique comment mesurer, minute par minute et couche par couche, la disponibilité de l'API cloud BLUETTI utilisée par Home Assistant. Le but : documenter les pannes avec des preuves horodatées et comparables entre plusieurs utilisateurs.

Contexte : [bluetti-official/bluetti-home-assistant#183](https://github.com/bluetti-official/bluetti-home-assistant/issues/183), les fils [bluetti-community#81](https://github.com/bluetti-community/bluetti-home-assistant/issues/81) et [bluetti-community#65](https://github.com/bluetti-community/bluetti-home-assistant/issues/65), et la discussion [bluetti-community#95](https://github.com/bluetti-community/bluetti-home-assistant/discussions/95).

Version de la sonde et du kit : **1.5.2** (affichée par `check` et en tête de chaque rapport). Le kit comprend une vue de tableau de bord prête à l'emploi (section 5.1). Le script, les entités et les rapports sont en anglais, pour que les relevés de tous les utilisateurs soient comparables ; seuls ce guide et la vue de tableau de bord existent aussi en français.

---

## 1. Le problème étudié

Par moments, la requête `GET /api/bluiotdata/ha/v1/deviceStates` sur `gw.bluettipower.com` ne répond plus du tout : aucun code HTTP ne revient, et la requête reste bloquée jusqu'au timeout du client. Pendant ce temps, le websocket de l'intégration reste connecté.

Ce qu'on sait déjà :

- Des fenêtres d'indisponibilité reviennent **vers 15:04–15:07 UTC** (23:04 heure de Chine). Elles ont été relevées les 11, 12, 13, 15 et 18 octobre 2026, ce qui évoque une tâche planifiée côté BLUETTI.
- Une autre fenêtre apparaît la nuit **vers 02:20 UTC**. Là, les requêtes répondent, mais l'appareil est renvoyé sans valeurs utilisables.
- Les commandes peuvent être acceptées par le cloud (HTTP 200, `msgCode 0`) sans être appliquées par l'appareil. Ce sujet est distinct, et la sonde ne le couvre pas.

La sonde permet de savoir **à quelle étape** une requête s'arrête, et si la panne touche tout le monde ou seulement certains nœuds.

---

## 2. Ce que mesure la sonde

Chaque minute, la sonde lance en parallèle :

| Mesure | Rôle |
|---|---|
| DNS A et AAAA via le résolveur système, 1.1.1.1, 8.8.8.8 et 223.5.5.5 (AliDNS) | IP renvoyée, chaîne CNAME, statut (dont NODATA) |
| `deviceStates` avec le jeton de Home Assistant | la requête qui pose problème, identique à celle de l'intégration |
| `deviceStates` sur **chaque IP** vue dans le DNS (`per_ip`) | indique si un seul nœud décroche |
| `deviceStates` sans jeton | si elle répond alors que la requête authentifiée bloque, c'est le backend qui décroche, pas la passerelle |
| `devices` avec jeton | même service, autre endpoint |
| Ouverture du websocket (HTTP 101 attendu) | confirme que la passerelle elle-même répond |
| `deviceStates` **avec** le jeton sur `gwde.bluettipower.com` (`other_gateways_auth`) | le backend derrière `gwde` répond-il quand celui derrière `gw` ne répond plus ? |
| `deviceStates` sans jeton sur `gwpry.bluettipower.com` | réponse d'une autre passerelle, sans passer par les données |

Chaque requête est classée selon l'étape où elle s'arrête :

| Étape | Signification |
|---|---|
| `no_tcp` | connexion TCP impossible |
| `no_tls` | TCP établi, mais pas de handshake TLS |
| `no_first_byte` | connexion établie, aucun octet de réponse : **le symptôme décrit dans #183** |
| `body_incomplete` | réponse commencée mais coupée |
| `answered` | réponse complète |

Une réponse complète mais plus lente que `SLOW_MS` (5 000 ms par défaut) est classée **`slow`** : un backend dégradé qui répond quand même. Elle compte comme un échec dans le rapport.

Sur une panne réseau, la sonde lance aussi une requête longue (jusqu'à 300 s, au plus une toutes les 30 minutes), pour mesurer combien de temps la passerelle garde la connexion ouverte. Le 3 novembre, elle s'est toujours terminée par un 504 de nginx au bout de 120 s.

**Confidentialité :**
- le jeton n'est jamais écrit dans les journaux, et il est passé à curl par un fichier temporaire, pas sur la ligne de commande ;
- les numéros de série sont masqués (`AC30…1234`) ;
- les journaux ne contiennent ni identifiants, ni valeurs de l'appareil, seulement le nombre de valeurs renvoyées.

---

## 3. Prérequis

- Home Assistant OS ou Supervised, avec l'intégration BLUETTI configurée et fonctionnelle : la sonde réutilise son jeton.
- Un accès aux fichiers de `/config`, via le module « Terminal & SSH », « Samba » ou « Studio Code Server ».

Les outils nécessaires (`bash`, `curl`, `jq`, `dig`) sont déjà présents dans le conteneur Home Assistant ; il n'y a rien à installer.

Fichiers du kit :

| Fichier | Emplacement |
|---|---|
| `config/bluetti-probe/bluetti-probe.sh` | `/config/bluetti-probe/bluetti-probe.sh` |
| `config/bluetti-probe/bluetti-probe.conf` | `/config/bluetti-probe/bluetti-probe.conf` |
| `config/packages/bluetti_probe.yaml` | `/config/packages/bluetti_probe.yaml` |
| `dashboard/bluetti_cloud_view_fr.yaml` (français) ou `dashboard/bluetti_cloud_view.yaml` (anglais) | facultatif : à coller dans un tableau de bord, pas à copier dans `/config` (section 5.1) |

---

## 4. Installation

### 4.1 Copier les fichiers

Copie le contenu du dossier `config/` du kit dans ton `/config`. Crée `/config/packages/` s'il n'existe pas.

### 4.2 Activer les paquets

Si ce n'est pas déjà fait, ajoute ceci dans `configuration.yaml` :

```yaml
homeassistant:
  packages: !include_dir_named packages
```

### 4.3 Renseigner la configuration

Édite `/config/bluetti-probe/bluetti-probe.conf` :

```bash
GATEWAY=""
SNS="NUMERO_SERIE_D_UN_APPAREIL_EN_LIGNE"
HA_CONFIG_ENTRIES="/config/.storage/core.config_entries"
```

- **`GATEWAY`** : laisse-le vide, et la sonde utilise la passerelle que l'intégration a enregistrée pour ton compte. Un jeton n'est accepté que par son propre centre de données. Si tu le fixes à la main (`https://gw.bluettipower.com`, `https://gwde.bluettipower.com` ou `https://gwpry.bluettipower.com`), `check` te prévient s'il diffère de celui de l'intégration.
- **`SNS`** : **un seul** numéro de série, celui d'un appareil **en ligne**.
  - L'API ne gère pas les listes : avec `SNS="A,B"`, elle ne renvoie que le premier appareil (vérifié le 3 novembre 2026). C'est cohérent avec l'intégration, qui fait une requête par appareil.
  - Pourquoi un appareil en ligne : pour un appareil hors ligne, le cloud renvoie un état stocké et passe probablement par un autre chemin interne. Il pourrait donc continuer de répondre pendant une panne qui bloque l'appareil en ligne.
  - Pour savoir lequel est en ligne : après une première passe, la sonde `devices` du journal liste tous les appareils du compte avec leur champ `online`.
- **`HA_CONFIG_ENTRIES`** : laisse cette valeur. Le jeton est relu à chaque passe, il est donc toujours à jour.

Les autres réglages ont des valeurs adaptées par défaut. Pour réduire la charge sur l'API, mets `COMPARE_GATEWAYS=""` : ça désactive la comparaison entre régions.

### 4.4 Charger et vérifier

1. Outils de développement → YAML → « Vérifier la configuration ».
2. Redémarre Home Assistant.
3. Outils de développement → Actions → `shell_command.bluetti_probe_check`. Coche « Renvoyer la réponse », puis exécute.
4. La dernière ligne de `stdout` doit être `=> ready`.

`check` vérifie aussi `SNS` en le comparant à la liste des appareils de ton compte (numéros de série masqués) :
- `EMPTY` ou `INVALID` (espace, virgule, guillemet) : corrige la ligne du fichier de configuration ;
- `NOT FOUND` : il y a une faute de frappe dans le numéro de série ;
- `WARNING: the two endpoints disagree` : `deviceStates` et `devices` ne donnent pas le même état pour l'appareil. Revérifie d'abord le numéro de série ; s'il est juste, ce désaccord mérite lui-même d'être signalé ;
- une note si l'appareil est hors ligne.

Ensuite, dans la minute qui suit, le capteur `sensor.bluetti_cloud_devicestates` doit prendre la valeur `ok`.

> Depuis le module « Terminal & SSH », `docker exec` n'est pas disponible : c'est normal. Utilise l'action ci-dessus, qui s'exécute dans le bon conteneur.

---

## 5. Ce que crée le paquet

| Entité ou action | Contenu |
|---|---|
| `sensor.bluetti_cloud_devicestates` | état : `ok`, `slow`, `empty`, `no_first_byte`, `no_tls`, `no_tcp`, `auth_error`, `http_XXX` ou `msgcode_XX` ; attributs : temps TCP/TLS/premier octet/total, IP, `per_ip`, DNS, état des autres sondes |
| `sensor.bluetti_cloud_devicestates_response_time` | temps total en ms, pour les graphiques |
| `binary_sensor.bluetti_cloud_devicestates_problem` | `on` dès que l'état n'est pas `ok`, pratique pour une alerte |
| `shell_command.bluetti_probe_check` | diagnostic de l'installation |
| `shell_command.bluetti_probe_report` / `_report_week` | rapport Markdown sur 24 h ou 7 jours |
| `script.bluetti_probe_report_24h` | affiche le rapport sur 24 h dans une notification persistante |

Le capteur passe par l'intégration `command_line`, dont le délai maximal est réglable, et non par `shell_command`, qui coupe tout au bout de 60 s sans exception.

### 5.1 Vue de tableau de bord (facultatif)

`dashboard/bluetti_cloud_view_fr.yaml` est une vue complète construite uniquement avec des cartes natives (vue en sections, titres, tuiles, jauge, Markdown, historique, statistiques). Aucune carte personnalisée ni module HACS n'est nécessaire. Une version anglaise, `bluetti_cloud_view.yaml`, a la même disposition.

Elle affiche :
1. **L'état du cloud** : un bandeau rouge, seulement pendant une panne, qui indique depuis quand elle dure et où elle se situe (passerelle qui répond mais pas le service des données, ou l'inverse), et si `gwde` répond au même moment ; les tuiles de panne et de résultat ; une jauge du temps de réponse (vert sous 1 s, orange jusqu'à 5 s, rouge au-delà) ; le résultat expliqué en clair.
2. **La dernière passe, couche par couche** : DNS, TCP, TLS, attente du premier octet, total, puis le code HTTP, le `msgCode`, le nœud BLUETTI et la réponse DNS.
3. **Où est la panne ?** : toutes les requêtes de la même passe côte à côte (`gw` et `gwde` avec le jeton, la passerelle sans jeton, le websocket, `gwpry`, chaque nœud), avec des pastilles 🟢 🟠 🔴.
4. **L'historique** : les dernières 24 h, et le temps de réponse sur 7 jours (moyenne et maximum par heure).
5. **Les outils** : un bouton qui génère le rapport sur 24 h.

Pour l'installer : ouvre un tableau de bord → ✏️ → ⋮ → **Éditeur de configuration brute**, et colle le contenu du fichier sous `views:`. Ou ajoute une vue vide, ⋮ → **Modifier en YAML**, et remplace son contenu par le fichier.

La vue utilise les identifiants d'entités d'une installation neuve. Si tu as installé la toute première version du paquet, en français, l'en-tête du fichier liste les trois identifiants à remplacer (`…_temps_de_reponse`, `…_en_panne`, `script.bluetti_probe_rapport`).

---

## 6. Lire les résultats

### Référence de fonctionnement normal

Relevé du 3 novembre 2026, de 09:22 à 09:30 UTC, depuis la France, résolveur système : 9 passes, aucun échec.

| Sonde | Médiane | Max |
|---|---|---|
| `deviceStates` | 195 ms | 245 ms |
| `deviceStates` sans jeton | 157 ms | 255 ms |
| `devices` | 224 ms | 326 ms |
| sans jeton sur `gwpry` | 765 ms | 815 ms |

Détail d'une requête normale : TCP environ 40 ms, TLS environ 100 ms, premier octet environ 55 ms après le TLS.

### Ce qu'on attend pendant une panne

| Observation | Interprétation probable |
|---|---|
| `deviceStates` en `no_first_byte`, sans jeton en `answered` | le backend de données décroche, la passerelle fonctionne |
| `deviceStates` et `devices` en `slow`, sans jeton et websocket rapides | le backend authentifié est dégradé, la passerelle fonctionne |
| les deux en `no_first_byte` ou `no_tls` | la passerelle elle-même ne répond plus |
| une seule IP en échec dans `per_ip` | panne limitée à un nœud |
| `empty` (en ligne, 0 valeur) | réponse vide : le motif de nuit vu dans #81 |
| DNS `NODATA` sur A | le gestionnaire de trafic n'a plus de nœud à proposer |
| `auth_error` (msgCode 805) | cette passerelle n'accepte pas le jeton : autre centre de données, ou jeton expiré. L'intégration communautaire le renouvelle et change de centre de données toute seule |

### Premier événement réel : 3 novembre 2026, 11:05–11:07 UTC

Même passe, même nœud européen (47.254.169.86), lancée à 11:05:40 UTC :

| Sonde | Premier octet |
|---|---|
| `deviceStates` avec jeton | **11,4 s** |
| `devices` avec jeton | **32,8 s** (au-delà du timeout de 30 s de l'intégration) |
| `deviceStates` sans jeton | 0,14 s |
| websocket | 0,16 s |

TCP et TLS étaient normaux partout. La passerelle répondait instantanément ; seules les requêtes authentifiées attendaient, ce qui désigne le backend derrière la passerelle. La passe suivante (11:06:40) a encore pris 13 à 24 s. À 11:07:40, `deviceStates` était revenu à 156 ms, mais `devices` prenait encore 14,7 s ; tout était normal à partir de 11:08:40. Ça correspond à la fenêtre de 11:06–11:08 UTC signalée le 12 octobre dans #183.

### Deuxième événement réel : 3 novembre 2026, à partir de 15:03 UTC (la fenêtre quotidienne)

À partir de 15:03:30 UTC, et encore à 18:27 à la fin du journal (au moins 3 h 24), **aucune requête authentifiée vers le nœud européen n'a reçu de réponse**, alors que sur le même nœud les requêtes sans jeton répondaient en 143 ms et le websocket en 154 ms. TCP et TLS sont restés normaux. Chaque requête longue s'est terminée par un **`504 Gateway Time-out` de nginx au bout de 120 s**, à travers huit instances différentes du répartiteur de charge (`via: HTTP/1.1 SLB.n`). Le backend de données derrière la passerelle était en panne ; la passerelle, le DNS et le réseau fonctionnaient. Le compte rendu a été publié dans bluetti-official#183.

### Particularités normales (ce ne sont pas des incidents)

- **AAAA en `NODATA`** : il n'existe pas d'adresse IPv6, seulement la chaîne CNAME.
- **Websocket fermé avec le code 1002 et « Server internal error »** juste après l'ouverture : la sonde ne parle pas le protocole STOMP qui suit, et le serveur ferme. C'est systématique. Un code de fermeture différent pendant un incident, en revanche, serait à noter.
- **`msgCode 801`** sur les requêtes sans jeton : « jeton d'accès manquant », c'est voulu.
- **AliDNS (223.5.5.5) lent ou sans réponse** depuis l'Europe : bruit sans effet sur Home Assistant.
- **`wrong_datacenter` dans `per_ip`** (`msgCode 805`, « veuillez vous connecter ») sur le nœud d'un autre continent : un jeton n'est valable que dans le centre de données de son compte. Voir ci-dessous.

### Le DNS n'envoie pas tout le monde au même endroit

`gw.bluettipower.com` est un CNAME vers `gtm-apigw.bluetti.ltd.`, un gestionnaire de trafic global. Le 3 novembre, le résolveur système, 8.8.8.8 et AliDNS renvoyaient **47.254.169.86** (le nœud européen), alors que 1.1.1.1 a renvoyé deux fois **47.253.45.39** (le nœud américain). Cloudflare ne transmet probablement pas la position du client, et le gestionnaire de trafic se trompe alors de continent.

À propos de l'astuce « rediriger `gw` vers `gwde` dans le DNS » : une réécriture DNS ne change que l'adresse IP ; la requête annonce toujours `gw.bluettipower.com`. Pour un utilisateur européen dont le résolveur renvoie déjà 47.254.169.86 pour `gw`, ça ne change rien. Ça aide en revanche ceux dont le résolveur envoyait `gw` vers le nœud américain (qui refuse les jetons européens avec `805` et répond plus lentement). Savoir si le backend derrière le **nom** `gwde` tient pendant la fenêtre quotidienne, c'est ce que mesure `other_gateways_auth`.

`gwpry.bluettipower.com` n'est **pas** ce nœud américain : le 6 novembre, ce nom résolvait vers 139.95.6.229. Les rapports des issues communautaires #65 et #92 montrent que des comptes européens y reçoivent `msgCode 0`, avec l'appareil `online=0` et SOC 0 ou sans données (#90). N'y configure donc pas un compte européen, et ne l'ajoute pas à `AUTH_COMPARE_GATEWAYS` : la sonde classerait cette réponse factice comme `ok`.

Deux utilisateurs peuvent donc parler à des nœuds différents selon leur résolveur DNS. Et ça compte : le 3 novembre, le nœud américain a refusé le jeton d'un compte européen **à chaque fois** (35 requêtes sur 35) avec `msgCode 805`, le même code qu'un jeton expiré. Un Home Assistant dont le résolveur envoie `gw` sur le mauvais continent verrait donc des erreurs « jeton expiré » qui n'ont rien à voir avec le jeton. C'est un mécanisme plausible derrière les refus 805 des comptes européens sur `gw`, que l'intégration communautaire a contournés en 1.5.0 en utilisant le centre de données propre à chaque compte (`gwde` pour l'Europe) ; ici, `gwde` a toujours résolu vers le nœud européen.

---

## 7. Produire et partager un rapport

Après une période qui couvre **15:00–16:30 UTC** (16:00–17:30 heure de Paris en hiver) :

- lance le script « BLUETTI probe report (24 h) » ; le rapport apparaît dans les notifications ;
- ou l'action `shell_command.bluetti_probe_report` (ou `_report_week`), en cochant « Renvoyer la réponse ».

Le rapport, en anglais, contient :
- la version de la sonde et la passerelle ;
- le tableau des fenêtres d'échec, en UTC ;
- l'état des autres sondes pendant ces fenêtres ;
- la durée réelle des blocages, mesurée par les requêtes longues.

**Pour coller un rapport dans GitHub, copie-le depuis le fichier, pas depuis la réponse de l'action.** Les outils de développement affichent la réponse en YAML, qui replie les lignes longues et ajoute des lignes vides : les tableaux Markdown sont cassés. Chaque rapport est aussi enregistré dans `/config/bluetti-probe/logs/report-last-1d.md` (ou `-7d.md`) : ouvre-le avec File editor, Studio Code Server ou Samba, et copie-le tel quel. Le rapport sur 7 jours peut être long à calculer sur un petit matériel ; Home Assistant coupe un `shell_command` au bout de 60 s.

Les journaux bruts sont dans `/config/bluetti-probe/logs/` : un fichier JSONL par jour, compressé à partir du lendemain, conservé 7 jours.

### Pour que les relevés soient comparables, joins à ton rapport

```text
Pays / FAI            :
Résolveur DNS de HA   : (box, Pi-hole, 1.1.1.1, …)
IP du nœud vue        : (attribut remote_ip, ex. 47.254.169.86)
Passerelle (GATEWAY)  : gw / gwde / gwpry
Région du compte      : UE / US / autre
Modèles d'appareils   :
Version HA            :
Version intégration   : (officielle ou communautaire, n° de version)
Période couverte (UTC):
```

Publie-le dans la [discussion #95](https://github.com/bluetti-community/bluetti-home-assistant/discussions/95), de préférence en anglais.

**À ne jamais partager :** le contenu de `core.config_entries`, ton jeton, ou les numéros de série complets.

---

## 8. Limites et précautions

- **Charge sur l'API** : la sonde ajoute environ 6 à 8 requêtes par minute, en plus des polls de l'intégration. Arrête-la quand l'enquête est finie, en commentant le bloc `command_line` du paquet.
- **Sauvegardes** : environ 8 Mo de journaux par jour, environ dix fois moins une fois compressés. Avec une rétention de 7 jours, compte environ 15 Mo dans `/config`, donc dans chaque sauvegarde Home Assistant.
- **Base de données** : le capteur change chaque minute, soit environ 1 440 états par jour. Tu peux l'exclure du recorder si besoin.
- **Arrêts de Home Assistant** : la sonde ne mesure rien pendant un redémarrage. Le même script fonctionne aussi sur une machine Linux séparée (LXC, VPS) avec `bluetti-probe.sh install`, puis un timer systemd. Il faut alors fournir le jeton dans un fichier (`TOKEN_FILE`) et le renouveler à la main, car il expire.
- **Jeton** : n'utilise jamais le `refresh_token` dans la sonde. Tu ferais tourner le jeton de Home Assistant à son insu.
- La sonde observe ; elle ne corrige rien. Les pannes elles-mêmes restent du ressort de BLUETTI.
