import { useEffect, useRef } from "react";
import mermaid from "mermaid";

mermaid.initialize({ startOnLoad: false, theme: "dark" });

interface Props {
  chart: string;
}

export default function MermaidDiagram({ chart }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chart || !ref.current) return;

    const renderId = `mermaid-${Date.now()}`;
    mermaid
      .render(renderId, chart)
      .then(({ svg }) => {
        if (ref.current) ref.current.innerHTML = svg;
      })
      .catch((err) => {
        if (ref.current) {
          ref.current.innerHTML = `<p class="error">Diagram render error: ${err.message}</p>`;
        }
      });
  }, [chart]);

  return <div ref={ref} />;
}