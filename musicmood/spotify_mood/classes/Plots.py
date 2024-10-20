import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 1, 500)

y1 = np.maximum(0, 1 - (1 / 0.3) * x)
y2 = np.maximum(0, 1 - (1 / 0.2) * np.abs(x - 0.3))
y3 = np.maximum(0, 1 - (1 / 0.2) * np.abs(x - 0.5))
y4 = np.maximum(0, 1 - (1 / 0.2) * np.abs(x - 0.7))
y5 = np.maximum(0, (1 / 0.3) * (x - 0.7))


plt.plot(x, y1, color='red', linewidth=2, label="low")
plt.plot(x, y2, color='yellow', linewidth=2, label="low-medium")
plt.plot(x, y3, color='green', linewidth=2, label="medium")
plt.plot(x, y4, color='blue', linewidth=2, label="medium-high")
plt.plot(x, y5, color='brown', linewidth=2, label="high")

plt.axhline(0, color='black', linewidth=3)
plt.axvline(0, color='black', linewidth=3)

plt.xlim([0, 1])
plt.ylim([0, 1])

plt.xlabel("x")
plt.ylabel("y")

plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0.)

plt.tight_layout()
plt.show()
