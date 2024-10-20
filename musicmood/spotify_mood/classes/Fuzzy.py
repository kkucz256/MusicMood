import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import matplotlib.pyplot as plt


class Fuzzy:
    def __init__(self):
        self.mood = ctrl.Antecedent(np.arange(0, 1.01, 0.1), 'mood')
        self.energy = ctrl.Consequent(np.arange(0, 1.01, 0.1), 'energy')
        self.valence = ctrl.Consequent(np.arange(0, 1.01, 0.1), 'valence')
        self.tempo = ctrl.Consequent(np.arange(60, 200.1, 10), 'tempo')
        self.loudness = ctrl.Consequent(np.arange(-60, 0.5, 5), 'loudness')
        self.danceability = ctrl.Consequent(np.arange(0, 1.01, 0.1), 'danceability')

        self._setup_fuzzy_logic()
        self.music_ctrl = ctrl.ControlSystem(self.rules)
        self.music_recommendation = ctrl.ControlSystemSimulation(self.music_ctrl)

    def _setup_fuzzy_logic(self):
        self.mood['smutny'] = fuzz.trimf(self.mood.universe, [0, 0, 0.5])
        self.mood['spokojny'] = fuzz.trimf(self.mood.universe, [0.25, 0.5, 0.75])
        self.mood['szczęśliwy'] = fuzz.trimf(self.mood.universe, [0.5, 1, 1])

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
            ctrl.Rule(self.mood['smutny'], (
                self.energy['low'], self.valence['low'], self.tempo['slow'], self.loudness['quiet'],
                self.danceability['low'])),

            ctrl.Rule(self.mood['spokojny'], (
                self.energy['medium'], self.valence['medium-high'], self.tempo['slow-medium'], self.loudness['medium'],
                self.danceability['medium'])),

            ctrl.Rule(self.mood['szczęśliwy'], (
                self.energy['high'], self.valence['high'], self.tempo['medium-fast'], self.loudness['medium-loud'],
                self.danceability['high']))
        ]

    def compute_recommendation(self, mood_value):
        self.music_recommendation.input['mood'] = mood_value
        self.music_recommendation.compute()

        return {
            'energy': self.music_recommendation.output['energy'],
            'valence': self.music_recommendation.output['valence'],
            'tempo': self.music_recommendation.output['tempo'],
            'loudness': self.music_recommendation.output['loudness'],
            'danceability': self.music_recommendation.output['danceability']
        }

    def print_results(self, mood_value):
        results = self.compute_recommendation(mood_value)
        print(f"\nParametry dla nastroju (mood={mood_value}):")
        print(f"Energy: {results['energy']}")
        print(f"Valence: {results['valence']}")
        print(f"Tempo: {results['tempo']} BPM")
        print(f"Loudness: {results['loudness']} dB")
        print(f"Danceability: {results['danceability']}")

    def print_membership(self, mood_value):
        smutny_membership = fuzz.interp_membership(self.mood.universe, self.mood['smutny'].mf, mood_value)
        spokojny_membership = fuzz.interp_membership(self.mood.universe, self.mood['spokojny'].mf, mood_value)
        szczesliwy_membership = fuzz.interp_membership(self.mood.universe, self.mood['szczęśliwy'].mf, mood_value)

        print(f"\nPrzynależności dla nastroju (mood={mood_value}):")
        print(f"Przynależność do 'smutny': {smutny_membership:.2f}")
        print(f"Przynależność do 'spokojny': {spokojny_membership:.2f}")
        print(f"Przynależność do 'szczęśliwy': {szczesliwy_membership:.2f}")
