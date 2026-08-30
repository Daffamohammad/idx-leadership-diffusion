import { useEffect } from "react"
import { createPortal } from "react-dom"

export default function CustomCursor() {
  useEffect(() => {
    const dot = document.createElement("div")
    const ring = document.createElement("div")
    dot.className = "cursor-dot"
    ring.className = "cursor-ring"
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reducedMotion) return;

    document.body.classList.add("custom-cursor-enabled");
    document.body.appendChild(dot)
    document.body.appendChild(ring)

    let mouseX = -100
    let mouseY = -100
    let ringX = -100
    let ringY = -100
    let raf: number

    const onMouseMove = (e: MouseEvent) => {
      mouseX = e.clientX
      mouseY = e.clientY
    }

    const onMouseOver = (e: MouseEvent) => {
      const target = e.target as Element
      if (target.closest("a, button, [role='button'], input, select, textarea, label")) {
        ring.classList.add("cursor-hover")
      }
    }

    const onMouseOut = (e: MouseEvent) => {
      const target = e.target as Element
      if (target.closest("a, button, [role='button'], input, select, textarea, label")) {
        ring.classList.remove("cursor-hover")
      }
    }

    const tick = () => {
      dot.style.transform = `translate(${mouseX}px, ${mouseY}px)`
      ringX += (mouseX - ringX) * 0.12
      ringY += (mouseY - ringY) * 0.12
      ring.style.transform = `translate(${ringX}px, ${ringY}px)`
      raf = requestAnimationFrame(tick)
    }

    document.addEventListener("mousemove", onMouseMove)
    document.addEventListener("mouseover", onMouseOver)
    document.addEventListener("mouseout", onMouseOut)
    raf = requestAnimationFrame(tick)

    return () => {
      document.removeEventListener("mousemove", onMouseMove)
      document.removeEventListener("mouseover", onMouseOver)
      document.removeEventListener("mouseout", onMouseOut)
      cancelAnimationFrame(raf)
      document.body.classList.remove("custom-cursor-enabled");
      if (document.body.contains(dot)) document.body.removeChild(dot)
      if (document.body.contains(ring)) document.body.removeChild(ring)
    }
  }, [])

  return createPortal(null, document.body)
}
