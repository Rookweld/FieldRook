import { KnowledgeLibrary } from "../../components/KnowledgeLibrary";
import "./Utility.css";

export function KnowledgeView() {
  return (
    <section className="sf-screen" aria-label="Knowledge">
      <div className="sf-utility">
        <div className="sf-eyebrow">Reference material</div>
        <h1>
          LESS NOISE.
          <br />
          MORE SIGNAL.
        </h1>
        <p>
          Saved resolutions from past investigations. Knowledge clarifies a case; it never
          overrules fresh evidence.
        </p>
        <div className="sf-utility-card">
          <KnowledgeLibrary />
        </div>
      </div>
    </section>
  );
}
