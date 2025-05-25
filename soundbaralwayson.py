import numpy as np # type: ignore
import sounddevice as sd # type: ignore
import soundfile as sf # type: ignore
import tkinter as tk
from tkinter import ttk
import tkinter.messagebox
import configparser
import os
import sys
import atexit
import logging

# Paramètres ok pour volume Windows à 75% Paramètres du son généré : wavetype=triangle, frequency=22000.00, volume=0.308

# --- Configuration du Logging ---
#logging.basicConfig(level=logging.INFO, 
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout)]) # Assure l'affichage dans la console pour .pyw

# --- Début: Logique pour instance unique ---
LOCK_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "soncontinueTK.lock")

def cleanup_lock_file():
    """Nettoie le fichier de verrouillage s'il existe."""
    logging.debug(f"Tentative de nettoyage du fichier de verrouillage : {LOCK_FILE_PATH}")
    if os.path.exists(LOCK_FILE_PATH):
        try:
            os.remove(LOCK_FILE_PATH)
            logging.info(f"Fichier de verrouillage '{LOCK_FILE_PATH}' supprimé.")
        except OSError as e:
            logging.error(f"Erreur lors de la suppression du fichier de verrouillage '{LOCK_FILE_PATH}': {e}", exc_info=True)

if os.path.exists(LOCK_FILE_PATH):
    logging.warning("Tentative de lancement d'une nouvelle instance alors qu'une autre est déjà en cours ou le fichier de verrouillage existe.")
    # Pour une application .pyw, une boîte de dialogue serait plus appropriée :
    tkinter.messagebox.showerror("Erreur", f"Une autre instance de l'application est déjà en cours d'exécution, ou le fichier de verrouillage n'a pas été supprimé : {LOCK_FILE_PATH}.")
    sys.exit(1)

try:
    with open(LOCK_FILE_PATH, "w") as lock_file:
        lock_file.write(str(os.getpid())) # Écrire le PID peut être utile pour des vérifications avancées
    atexit.register(cleanup_lock_file)
    logging.info(f"Fichier de verrouillage '{LOCK_FILE_PATH}' créé pour le PID {os.getpid()}.")
except IOError as e:
    logging.critical(f"Impossible de créer le fichier de verrouillage : {e}", exc_info=True)
    sys.exit(1)
# --- Fin: Logique pour instance unique ---

sample_rate = 44100
playing = False
config_file = "settings.ini"
test_file = "test.wav" # Assurez-vous que ce fichier existe ou gérez son absence


DEFAULT_SETTINGS_ON_RESET = {
    "wave_type": "triangle",
    "frequency": "20000",
    "volume": "0.006",
    "autostart_sound": "0",
    "start_minimized": "0"
}

def load_settings():
    """Charge les paramètres depuis le fichier settings.ini."""
    logging.info("Chargement des paramètres depuis settings.ini.")
    config = configparser.ConfigParser()
    if os.path.exists(config_file):
        config.read(config_file)
        return config["Settings"]
    return DEFAULT_SETTINGS_ON_RESET.copy() # Utiliser les valeurs de réinitialisation comme défaut initial

def save_settings():
    """Sauvegarde les paramètres actuels dans settings.ini."""
    logging.info("Sauvegarde des paramètres dans settings.ini.")
    config = configparser.ConfigParser()
    config["Settings"] = {
        "wave_type": wave_type_var.get(),
        "frequency": str(int(frequency_var.get())), # Convertir le float/int du slider en chaîne pour la sauvegarde
        "volume": str(volume_var.get()), # Convertir le float du slider en chaîne pour la sauvegarde
        "autostart_sound": "1" if autostart_sound_var.get() else "0",
        "start_minimized": "1" if start_minimized_var.get() else "0"
    }
    with open(config_file, "w") as configfile:
        config.write(configfile)

def reload_settings():
    """Recharge les paramètres depuis le fichier settings.ini et les applique."""
    logging.info("Rechargement des paramètres depuis settings.ini.")
    settings = load_settings()
    wave_type_var.set(settings["wave_type"])
    frequency_var.set(float(settings.get("frequency", 20000.0))) # Convertir la chaîne en float pour le slider
    volume_var.set(float(settings.get("volume", 0.5))) # Convertir la chaîne en float pour le slider
    autostart_sound_var.set(settings.get("autostart_sound", "0") == "1")
    start_minimized_var.set(settings.get("start_minimized", "0") == "1")
    # Mettre à jour manuellement les labels des curseurs
    update_frequency_label(frequency_var.get())
    update_volume_label(volume_var.get())

def generate_waveform(wave_type, frequency, volume, duration=1):
    """Génère une forme d'onde selon le type choisi."""
    logging.debug(f"Génération de la forme d'onde : type={wave_type}, freq={frequency}, vol={volume}, dur={duration}s")
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    if wave_type == "sine":
        waveform = np.sin(2 * np.pi * frequency * t)
    elif wave_type == "square":
        waveform = np.sign(np.sin(2 * np.pi * frequency * t))
    elif wave_type == "sawtooth":
        waveform = 2 * (t * frequency - np.floor(t * frequency + 0.5))
    elif wave_type == "triangle":
        waveform = 2 * np.abs(2 * (t * frequency - np.floor(t * frequency + 0.5))) - 1
    else:
        raise ValueError("Type d'onde non supporté")
    
    return waveform * volume

def update_sound():
    """Met à jour le son généré en boucle si actif."""
    logging.debug("Mise à jour du son généré.")

    try:
        wave_type = wave_type_var.get()
        frequency = frequency_var.get()
        volume = volume_var.get()
        waveform = generate_waveform(wave_type, frequency, volume)
        logging.debug(f"Paramètres du son généré : wavetype={wave_type}, frequency={frequency:.2f}, volume={volume:.3f}")
        sd.play(waveform, samplerate=sample_rate, loop=True)

    except ValueError as e:
        logging.error(f"Erreur de valeur (fréquence/volume) lors de la mise à jour du son : {e}", exc_info=True)
        stop_sound() # Arrêter le son si les paramètres sont invalides
        tkinter.messagebox.showerror("Erreur de paramètre", "La fréquence ou le volume entré est invalide.")
def start_sound():
    """Démarre la lecture du son généré."""
    logging.info("Démarrage du son généré.")
    start_button.config(state=tk.DISABLED)
    stop_button.config(state=tk.NORMAL)
    update_sound()

def stop_sound():
    """Arrête la lecture du son généré."""
    logging.info("Arrêt du son généré.")
    sd.stop()
    start_button.config(state=tk.NORMAL)
    stop_button.config(state=tk.DISABLED)

def play_test_sound():
    """Arrête le son généré, joue test.wav, puis reprend le son généré."""
    logging.info("Lecture du son de test.")


    if os.path.exists(test_file):
        try:
            data, file_samplerate = sf.read(test_file)
            sd.play(data, file_samplerate)
            sd.wait()  # Attend la fin de la lecture du fichier test
            start_sound()  # Continuez avec le son généré
        except Exception as e:
            logging.error(f"Erreur lors de la lecture du fichier de test '{test_file}': {e}", exc_info=True)
            # Afficher une boîte de message d'erreur à l'utilisateur
            tkinter.messagebox.showerror("Erreur de lecture", f"Impossible de lire le fichier test '{test_file}': {e}")
    else:
        logging.warning(f"Fichier de test '{test_file}' non trouvé.")
        # Informer l'utilisateur que le fichier test est manquant

settings = load_settings()

root = tk.Tk()
root.title("Générateur de Son")
root.geometry("460x430") # Taille légèrement augmentée pour plus de confort

def on_app_exit():
    """Fonction de nettoyage à la fermeture de l'application."""
    stop_sound() # S'assurer que le son est arrêté
    cleanup_lock_file() # S'assurer que le fichier de verrouillage est supprimé
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_app_exit) # Gérer la fermeture via le bouton de la fenêtre

wave_type_var = tk.StringVar(value=settings["wave_type"])
frequency_var = tk.DoubleVar(value=float(settings.get("frequency", 20000.0))) # Utiliser DoubleVar pour le Scale
volume_var = tk.DoubleVar(value=float(settings.get("volume", 0.5))) # Utiliser DoubleVar pour le Scale
autostart_sound_var = tk.BooleanVar(value=(settings.get("autostart_sound", "0") == "1"))
start_minimized_var = tk.BooleanVar(value=(settings.get("start_minimized", "0") == "1"))
# --- Fonction pour la boîte "À propos" ---
def show_about_dialog():
    """Affiche la boîte de dialogue 'À propos'."""
    tkinter.messagebox.showinfo(
        "À propos de Générateur de Son",
        "Générateur de Son Continu v1.0\n\n"
        "Créé avec Python et Tkinter.\n"
        "Permet de générer différents types d'ondes sonores."
    )

# --- Fonction pour réinitialiser les paramètres ---
def reset_settings_to_default():
    """Réinitialise les paramètres aux valeurs par défaut et les sauvegarde."""
    stop_sound() # Arrêter le son en cours
    # Appliquer les valeurs par défaut aux variables Tkinter
    wave_type_var.set(DEFAULT_SETTINGS_ON_RESET["wave_type"])
    frequency_var.set(float(DEFAULT_SETTINGS_ON_RESET["frequency"])) # DoubleVar attend un float
    volume_var.set(float(DEFAULT_SETTINGS_ON_RESET["volume"])) # DoubleVar attend un float
    autostart_sound_var.set(DEFAULT_SETTINGS_ON_RESET["autostart_sound"] == "1") # BooleanVar attend un bool
    start_minimized_var.set(DEFAULT_SETTINGS_ON_RESET["start_minimized"] == "1") # Sera False
    # Mettre à jour manuellement les labels des curseurs après la réinitialisation
    update_frequency_label(frequency_var.get())
    update_volume_label(volume_var.get())
    save_settings() # Sauvegarder les nouveaux paramètres par défaut dans settings.ini
    tkinter.messagebox.showinfo(
        "Réinitialisation",
        f"Les paramètres ont été réinitialisés aux valeurs par défaut et sauvegardés.\n"
        f"Paramètres actuels :\n"
        f"  Type d'onde : {wave_type_var.get()}\n" # Utiliser .get() pour les StringVar
        f"  Fréquence : {int(frequency_var.get())} Hz\n" # Afficher comme entier pour la fréquence
        f"  Volume : {volume_var.get():.3f}\n" # :.3f pour formater le float du volume
        f"  Démarrer son au lancement : {'Oui' if autostart_sound_var.get() else 'Non'}\n"
        f"  Démarrer en mode réduit : {'Oui' if start_minimized_var.get() else 'Non'}"
    )

# --- Création du menu ---
menubar = tk.Menu(root)
root.config(menu=menubar)

file_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Fichier", menu=file_menu)
file_menu.add_command(label="Charger les paramètres", command=reload_settings)
file_menu.add_command(label="Sauvegarder les paramètres", command=save_settings)
file_menu.add_separator()
file_menu.add_command(label="Réinitialisation", command=reset_settings_to_default)
file_menu.add_separator()
file_menu.add_command(label="Quitter", command=on_app_exit)

help_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Aide", menu=help_menu)
help_menu.add_command(label="À propos", command=show_about_dialog)

# --- Widgets principaux ---
main_frame = ttk.Frame(root, padding="10")
main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

# Empêcher la fenêtre root de se redimensionner en fonction du contenu de main_frame
root.grid_propagate(False)
# Optionnel: Empêcher l'utilisateur de redimensionner la fenêtre
root.resizable(False, False)

# --- Section Type d'onde avec Boutons Radio ---
wave_type_label = ttk.Label(main_frame, text="Type d'onde:")
wave_type_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))

wave_types = ["sine", "square", "sawtooth", "triangle"]
radio_button_frame = ttk.Frame(main_frame) # Un sous-frame pour les boutons radio
radio_button_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=2)

for i, wt in enumerate(wave_types):
    rb = ttk.Radiobutton(radio_button_frame, text=wt.capitalize(), variable=wave_type_var, value=wt)
    rb.pack(side=tk.LEFT, padx=5) # pack est plus simple pour une ligne de boutons

# --- Section Valeur de fréquence avec Curseur ---
ttk.Label(main_frame, text="Fréquence (Hz)").grid(row=2, column=0, sticky=tk.W, pady=2)

frequency_controls_frame = ttk.Frame(main_frame)
frequency_controls_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2)

frequency_value_label = ttk.Label(frequency_controls_frame, text=f"{int(frequency_var.get())}", width=6) # Label pour la valeur
frequency_value_label.pack(side=tk.RIGHT, padx=(5,0))

def update_frequency_label(value):
    """Met à jour le label d'affichage de la fréquence."""
    frequency_value_label.config(text=f"{int(float(value))}") # Afficher comme entier

frequency_scale = ttk.Scale(
    frequency_controls_frame,
    variable=frequency_var,
    from_=20.0,  # Fréquence minimale (ex: 20 Hz)
    to=22000.0, # Fréquence maximale (ex: 22000 Hz)
    orient=tk.HORIZONTAL,
    command=update_frequency_label,
    length=300) # Longueur du curseur en pixels
frequency_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)

# --- Curseur de Volume et affichage de sa valeur ---
ttk.Label(main_frame, text="Volume").grid(row=3, column=0, sticky=tk.W, pady=2)
volume_controls_frame = ttk.Frame(main_frame) # Un sous-frame pour le curseur et son label
volume_controls_frame.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=2)
volume_value_label = ttk.Label(volume_controls_frame, text=f"{volume_var.get():.3f}", width=5) # Label pour afficher la valeur
volume_value_label.pack(side=tk.RIGHT, padx=(5, 0))

def update_volume_label(value):
    """Met à jour le label d'affichage du volume."""
    volume_value_label.config(text=f"{float(value):.3f}")

# Remplacer ttk.Entry par ttk.Scale pour le volume
volume_scale = ttk.Scale(
    volume_controls_frame, # Mettre le curseur dans le nouveau frame
    variable=volume_var,
    from_=0.0,
    to=1.0,
    orient=tk.HORIZONTAL,
    command=update_volume_label, # Appeler update_volume_label quand la valeur change
    length=300) # Longueur du curseur en pixels
volume_scale.pack(side=tk.LEFT, fill=tk.X, expand=True) # pack pour s'adapter au frame

# Boutons d'action
start_button = ttk.Button(main_frame, text="Démarrer", command=start_sound)
start_button.grid(row=4, column=0, pady=5)
stop_button = ttk.Button(main_frame, text="Arrêter", command=stop_sound)
stop_button.grid(row=4, column=1, pady=5)

ttk.Checkbutton(main_frame, text="Démarrer le son au lancement", variable=autostart_sound_var).grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=10)
ttk.Checkbutton(main_frame, text="Démarrer en mode réduit", variable=start_minimized_var).grid(row=7, column=0, columnspan=2, sticky=tk.W, pady=5)

ttk.Button(main_frame, text="TestSon", command=play_test_sound).grid(row=8, column=0, columnspan=2, pady=5)

# État initial des boutons

if autostart_sound_var.get():
    # start_sound() sera appelé ci-dessous et gérera l'état des boutons
    pass # Les états seront gérés par l'appel à start_sound()
else:
    stop_button.config(state=tk.DISABLED)

if autostart_sound_var.get():
    start_sound()

if start_minimized_var.get():
    root.iconify() # Minimise la fenêtre

root.mainloop()