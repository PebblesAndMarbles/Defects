import numpy as np
from scipy import ndimage
from scipy.fft import fft2, fftshift
import matplotlib.pyplot as plt
from PIL import Image

# ── Load image ──────────────────────────────────────────────────────────────
path = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\images\defects\AME403_PM4\260616_2332_D610232_178_BEEP_8M6CL_41_2.jpg"

img = Image.open(path).convert('L')          # grayscale
arr = np.array(img, dtype=np.float32)

print(f"Image shape: {arr.shape}")           # (H, W)

# ── Define ROI  ──────────────────────────────────────────────────────────────
# "clean" horizontal band above the dark timestamp bar
# Adjust y0/y1 if needed after inspecting the image
H, W = arr.shape

y0, y1 = int(H * 0.67), int(H * 0.73)      # ~rows 430-467 for 640-tall image
x0, x1 = int(W * 0.05), int(W * 0.95)      # avoid left/right edges

roi = arr[y0:y1, x0:x1]
print(f"ROI shape : {roi.shape}  (y={y0}:{y1}, x={x0}:{x1})")

# ── Optional: show ROI location ──────────────────────────────────────────────
fig0, ax0 = plt.subplots(figsize=(8, 5))
ax0.imshow(arr, cmap='gray', vmin=0, vmax=255)
rect = plt.Rectangle((x0, y0), x1-x0, y1-y0,
                      edgecolor='cyan', facecolor='none', lw=2)
ax0.add_patch(rect)
ax0.set_title("Full image — cyan box = ROI")
plt.tight_layout()
plt.savefig("roi_location.png", dpi=150)
plt.show()

# ── 2-D FFT ──────────────────────────────────────────────────────────────────
# subtract mean & apply 2-D Hann window to reduce spectral leakage
roi_zm = roi - roi.mean()

wy = np.hanning(roi.shape[0])
wx = np.hanning(roi.shape[1])
window2d = np.outer(wy, wx)

roi_w = roi_zm * window2d

F   = fft2(roi_w)
Fsh = fftshift(F)
PSD = np.abs(Fsh) ** 2                      # power spectral density

PSD_log = np.log10(PSD + 1e-6)             # log scale for display

# ── Frequency axes (units = cycles / pixel) ──────────────────────────────────
nr, nc = roi.shape
freq_r = fftshift(np.fft.fftfreq(nr))      # vertical   freq axis
freq_c = fftshift(np.fft.fftfreq(nc))      # horizontal freq axis

# ── Plot 2-D PSD ─────────────────────────────────────────────────────────────
fig1, ax1 = plt.subplots(figsize=(7, 5))
im = ax1.imshow(PSD_log,
                extent=[freq_c[0], freq_c[-1], freq_r[-1], freq_r[0]],
                cmap='inferno', aspect='auto')
plt.colorbar(im, ax=ax1, label='log10(PSD)')
ax1.set_xlabel("Horizontal spatial freq  [cycles / pixel]")
ax1.set_ylabel("Vertical spatial freq    [cycles / pixel]")
ax1.set_title("2-D PSD — bare SiO substrate ROI")
plt.tight_layout()
plt.savefig("psd_2d.png", dpi=150)
plt.show()

# ── 1-D horizontal profile of PSD (average over vertical freq band) ───────────
# collapse vertically — gives horizontal texture periodicity
psd_h = PSD.mean(axis=0)                   # shape (nc,)
psd_h_log = np.log10(psd_h + 1e-6)

# positive frequencies only
half = nc // 2
freq_pos = freq_c[half:]                   # 0 … +0.5 cyc/px
psd_pos  = psd_h_log[half:]

# find dominant horizontal period
peak_idx = np.argmax(psd_pos[1:]) + 1      # skip DC
peak_freq = freq_pos[peak_idx]
peak_period_px = 1.0 / peak_freq if peak_freq > 0 else np.inf

print(f"\nDominant horizontal texture:")
print(f"  Spatial frequency : {peak_freq:.4f}  cycles/pixel")
print(f"  Period            : {peak_period_px:.1f}  pixels")
print(f"  Period / img width: {peak_period_px / W:.4f}")

fig2, ax2 = plt.subplots(figsize=(8, 4))
ax2.plot(freq_pos, psd_pos, lw=1.2, color='steelblue')
ax2.axvline(peak_freq, color='red', ls='--',
            label=f"peak  {peak_freq:.4f} cyc/px  ({peak_period_px:.1f} px)")
ax2.set_xlabel("Horizontal spatial freq  [cycles / pixel]")
ax2.set_ylabel("log10(PSD)  [arb]")
ax2.set_title("1-D horizontal PSD — bare SiO substrate texture")
ax2.legend()
plt.tight_layout()
plt.savefig("psd_1d_horizontal.png", dpi=150)
plt.show()

# ── Radially-averaged PSD (isotropic texture estimate) ───────────────────────
fc_2d, fr_2d = np.meshgrid(freq_c, freq_r)
radial_freq   = np.sqrt(fc_2d**2 + fr_2d**2)

r_bins  = np.linspace(0, 0.5, 128)
r_mid   = 0.5 * (r_bins[:-1] + r_bins[1:])
psd_rad = np.zeros(len(r_mid))

for i, (r0, r1) in enumerate(zip(r_bins[:-1], r_bins[1:])):
    mask = (radial_freq >= r0) & (radial_freq < r1)
    if mask.sum() > 0:
        psd_rad[i] = PSD[mask].mean()

psd_rad_log = np.log10(psd_rad + 1e-6)

fig3, ax3 = plt.subplots(figsize=(8, 4))
ax3.plot(r_mid, psd_rad_log, lw=1.2, color='darkorange')
ax3.set_xlabel("Radial spatial freq  [cycles / pixel]")
ax3.set_ylabel("log10(mean PSD)  [arb]")
ax3.set_title("Radially-averaged PSD — bare SiO substrate texture")
plt.tight_layout()
plt.savefig("psd_radial.png", dpi=150)
plt.show()

print("\nDone — saved: roi_location.png, psd_2d.png, psd_1d_horizontal.png, psd_radial.png")