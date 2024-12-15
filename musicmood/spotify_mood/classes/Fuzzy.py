import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import matplotlib.pyplot as plt


class Fuzzy:
    def __init__(self):
        self.mood = ctrl.Antecedent(np.arange(0, 1.01, 0.1), 'mood')
        self.time_of_day = ctrl.Antecedent(np.arange(0, 24.1, 1), 'time_of_day')

        self.energy = ctrl.Consequent(np.arange(0, 1.01, 0.1), 'energy')
        self.valence = ctrl.Consequent(np.arange(0, 1.01, 0.1), 'valence')
        self.tempo = ctrl.Consequent(np.arange(60, 200.1, 10), 'tempo')
        self.loudness = ctrl.Consequent(np.arange(-60, 0.5, 5), 'loudness')
        self.danceability = ctrl.Consequent(np.arange(0, 1.01, 0.1), 'danceability')

        self._setup_fuzzy_logic()
        self.music_ctrl = ctrl.ControlSystem(self.rules)
        self.music_recommendation = ctrl.ControlSystemSimulation(self.music_ctrl)

    def _setup_fuzzy_logic(self):
        self.mood['smutny'] = fuzz.trapmf(self.mood.universe, [0, 0, 0.2, 0.4])
        self.mood['spokojny'] = fuzz.trapmf(self.mood.universe, [0.15, 0.35, 0.65, 0.85])
        self.mood['szczęśliwy'] = fuzz.trapmf(self.mood.universe, [0.6, 0.8, 1, 1])

        self.time_of_day['rano'] = fuzz.trapmf(self.time_of_day.universe, [0, 0, 6, 12])
        self.time_of_day['popołudnie'] = fuzz.trapmf(self.time_of_day.universe, [10, 12, 16, 18])
        self.time_of_day['wieczór'] = fuzz.trapmf(self.time_of_day.universe, [16, 18, 24, 24])

        self.energy['low'] = fuzz.trimf(self.energy.universe, [0, 0, 0.3])
        self.energy['low-medium'] = fuzz.trimf(self.energy.universe, [0.1, 0.3, 0.5])
        self.energy['medium'] = fuzz.trimf(self.energy.universe, [0.3, 0.5, 0.7])
        self.energy['medium-high'] = fuzz.trimf(self.energy.universe, [0.5, 0.7, 0.9])
        self.energy['high'] = fuzz.trimf(self.energy.universe, [0.7, 1, 1])

        self.valence['low'] = fuzz.trimf(self.valence.universe, [0, 0, 0.3])
        self.valence['low-medium'] = fuzz.trimf(self.valence.universe, [0.1, 0.3, 0.5])
        self.valence['medium'] = fuzz.trimf(self.valence.universe, [0.3, 0.5, 0.7])
        self.valence['medium-high'] = fuzz.trimf(self.valence.universe, [0.5, 0.7, 0.9])
        self.valence['high'] = fuzz.trimf(self.valence.universe, [0.7, 1, 1])

        self.tempo['slow'] = fuzz.trimf(self.tempo.universe, [60, 60, 100])
        self.tempo['slow-medium'] = fuzz.trimf(self.tempo.universe, [80, 100, 120])
        self.tempo['medium'] = fuzz.trimf(self.tempo.universe, [100, 120, 140])
        self.tempo['medium-fast'] = fuzz.trimf(self.tempo.universe, [120, 140, 160])
        self.tempo['fast'] = fuzz.trimf(self.tempo.universe, [140, 200, 200])

        self.loudness['quiet'] = fuzz.trimf(self.loudness.universe, [-60, -60, -30])
        self.loudness['quiet-medium'] = fuzz.trimf(self.loudness.universe, [-50, -40, -20])
        self.loudness['medium'] = fuzz.trimf(self.loudness.universe, [-40, -20, 0])
        self.loudness['medium-loud'] = fuzz.trimf(self.loudness.universe, [-20, -10, 0])
        self.loudness['loud'] = fuzz.trimf(self.loudness.universe, [-10, 0, 0])

        self.danceability['low'] = fuzz.trimf(self.danceability.universe, [0, 0, 0.3])
        self.danceability['low-medium'] = fuzz.trimf(self.danceability.universe, [0.1, 0.3, 0.5])
        self.danceability['medium'] = fuzz.trimf(self.danceability.universe, [0.3, 0.5, 0.7])
        self.danceability['medium-high'] = fuzz.trimf(self.danceability.universe, [0.5, 0.7, 0.9])
        self.danceability['high'] = fuzz.trimf(self.danceability.universe, [0.7, 1, 1])

        self.rules = [
            ctrl.Rule(self.mood['smutny'] & self.time_of_day['rano'], (
                self.energy['low-medium'], self.valence['low-medium'], self.tempo['slow'],
                self.loudness['quiet-medium'], self.danceability['low'])),

            ctrl.Rule(self.mood['smutny'] & self.time_of_day['popołudnie'], (
                self.energy['low-medium'], self.valence['low-medium'], self.tempo['slow-medium'],
                self.loudness['quiet-medium'], self.danceability['low-medium'])),

            ctrl.Rule(self.mood['smutny'] & self.time_of_day['wieczór'], (
                self.energy['low'], self.valence['low-medium'], self.tempo['slow'],
                self.loudness['quiet'], self.danceability['low-medium'])),

            ctrl.Rule(self.mood['spokojny'] & self.time_of_day['rano'], (
                self.energy['medium'], self.valence['medium'], self.tempo['slow-medium'],
                self.loudness['medium'], self.danceability['low-medium'])),

            ctrl.Rule(self.mood['spokojny'] & self.time_of_day['popołudnie'], (
                self.energy['medium'], self.valence['medium'], self.tempo['medium'],
                self.loudness['medium'], self.danceability['medium'])),

            ctrl.Rule(self.mood['spokojny'] & self.time_of_day['wieczór'], (
                self.energy['low-medium'], self.valence['medium'], self.tempo['slow-medium'],
                self.loudness['quiet-medium'], self.danceability['medium'])),

            ctrl.Rule(self.mood['szczęśliwy'] & self.time_of_day['rano'], (
                self.energy['high'], self.valence['high'], self.tempo['medium-fast'],
                self.loudness['loud'], self.danceability['medium-high'])),

            ctrl.Rule(self.mood['szczęśliwy'] & self.time_of_day['popołudnie'], (
                self.energy['high'], self.valence['high'], self.tempo['fast'],
                self.loudness['loud'], self.danceability['high'])),

            ctrl.Rule(self.mood['szczęśliwy'] & self.time_of_day['wieczór'], (
                self.energy['medium-high'], self.valence['high'], self.tempo['medium-fast'],
                self.loudness['medium-loud'], self.danceability['high']))
        ]

    def compute_recommendation(self, mood_value, time_of_day):
        self.music_recommendation.input['mood'] = mood_value
        self.music_recommendation.input['time_of_day'] = time_of_day
        self.music_recommendation.compute()

        return {
            'energy': self.music_recommendation.output['energy'],
            'valence': self.music_recommendation.output['valence'],
            'tempo': self.music_recommendation.output['tempo'],
            'loudness': self.music_recommendation.output['loudness'],
            'danceability': self.music_recommendation.output['danceability']
        }

    def print_results(self, mood_value, time_of_the_day):
        results = self.compute_recommendation(mood_value, time_of_the_day)
        print(f"\nParametry dla nastroju (mood={mood_value}) i pory dnia {time_of_the_day}:")
        print(f"Energy: {results['energy']}")
        print(f"Valence: {results['valence']}")
        print(f"Tempo: {results['tempo']} BPM")
        print(f"Loudness: {results['loudness']} dB")
        print(f"Danceability: {results['danceability']}")

    def plot_membership_functions(self):
        # Rysowanie funkcji przynależności dla zmiennej 'mood' oraz 'time_of_day'
        plt.figure(figsize=(12, 10))

        # Wykres dla 'mood'
        plt.subplot(2, 1, 1)
        plt.plot(self.mood.universe, self.mood['smutny'].mf, label='smutny', color='blue')
        plt.plot(self.mood.universe, self.mood['spokojny'].mf, label='spokojny', color='green')
        plt.plot(self.mood.universe, self.mood['szczęśliwy'].mf, label='szczęśliwy', color='orange')

        plt.axhline(0, color='black', linewidth=1)
        plt.axvline(0, color='black', linewidth=1)

        plt.title("Funkcje przynależności zmiennej rozmytej 'nastrój'")
        plt.xlabel("Wartość nastroju")
        plt.ylabel("Stopień przynależności")
        plt.legend(loc="upper right")
        plt.grid(True, which='both', linestyle='--', linewidth=0.5)

        plt.subplot(2, 1, 2)
        plt.plot(self.time_of_day.universe, self.time_of_day['rano'].mf, label='rano', color='purple')
        plt.plot(self.time_of_day.universe, self.time_of_day['popołudnie'].mf, label='popołudnie', color='red')
        plt.plot(self.time_of_day.universe, self.time_of_day['wieczór'].mf, label='wieczór', color='brown')

        plt.axhline(0, color='black', linewidth=1)
        plt.axvline(0, color='black', linewidth=1)

        plt.title("Funkcje przynależności zmiennej rozmytej 'pora_dnia'")
        plt.xlabel("Godzina dnia")
        plt.ylabel("Stopień przynależności")
        plt.legend(loc="upper right")
        plt.grid(True, which='both', linestyle='--', linewidth=0.5)

        plt.tight_layout()
        plt.show()

if __name__ == "__main__":
    fuzzy_system = Fuzzy()
    fuzzy_system.plot_membership_functions()