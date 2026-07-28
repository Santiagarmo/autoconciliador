import { onUnmounted, type Ref, ref, watch } from "vue";

/**
 * Anima un valor numérico entre su estado anterior y el nuevo con
 * requestAnimationFrame, en vez de saltar directo al número — refuerza que
 * los StatCard reflejan datos vivos, no texto estático. Arranca siempre
 * desde el valor mostrado actualmente (no desde 0), porque los stats se
 * vuelven a calcular al filtrar y un reinicio a 0 en cada filtro sería
 * ruido, no señal.
 *
 * Respeta `prefers-reduced-motion`: en ese caso salta directo al valor
 * final sin animar.
 */
export function useCountUp(source: Ref<number>, duration = 600): Ref<number> {
  const displayed = ref(source.value);

  const prefersReducedMotion =
    typeof window !== "undefined" && window.matchMedia
      ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
      : false;

  let frame: number | null = null;

  watch(source, (next) => {
    if (frame !== null) cancelAnimationFrame(frame);

    if (prefersReducedMotion) {
      displayed.value = next;
      return;
    }

    const from = displayed.value;
    const delta = next - from;
    if (delta === 0) return;

    const start = performance.now();

    function tick(now: number): void {
      const elapsed = now - start;
      const t = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
      displayed.value = Math.round(from + delta * eased);

      if (t < 1) {
        frame = requestAnimationFrame(tick);
      } else {
        displayed.value = next;
        frame = null;
      }
    }

    frame = requestAnimationFrame(tick);
  });

  onUnmounted(() => {
    if (frame !== null) cancelAnimationFrame(frame);
  });

  return displayed;
}
