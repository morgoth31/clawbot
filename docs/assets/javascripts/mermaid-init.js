// Initialisation de Mermaid pour la documentation Clawbot.
//
// mermaid.min.js (10.9.1) est embarqué dans assets/javascripts/ : aucun accès
// réseau n'est requis, le site fonctionne hors ligne.
//
// Le rendu n'utilise pas mermaid.run() : les blocs produits par pymdownx
// contiennent un élément <code> interne, et run() analyse innerHTML — d'où une
// erreur de syntaxe systématique. On lit donc textContent, puis on injecte le
// SVG produit par mermaid.render().
(function () {
  var configured = false;
  var counter = 0;

  function configure() {
    if (configured || typeof mermaid === "undefined") {
      return;
    }
    mermaid.initialize({
      startOnLoad: false,
      theme: "base",
      securityLevel: "loose",
      fontFamily:
        '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
      themeVariables: {
        primaryColor: "#e8eaf6",
        primaryTextColor: "#1a237e",
        primaryBorderColor: "#5c6bc0",
        lineColor: "#5c6bc0",
        secondaryColor: "#fce4ec",
        tertiaryColor: "#e8f5e9",
        noteBkgColor: "#fff9c4",
        noteBorderColor: "#fbc02d",
      },
      flowchart: { curve: "basis", htmlLabels: true },
      sequence: { useMaxWidth: true, mirrorActors: false },
    });
    configured = true;
  }

  function renderAll() {
    if (typeof mermaid === "undefined") {
      return;
    }
    configure();
    var blocks = document.querySelectorAll(".mermaid:not([data-rendered])");
    Array.prototype.forEach.call(blocks, function (el) {
      var source = el.textContent || "";
      if (!source.trim()) {
        return;
      }
      el.setAttribute("data-rendered", "1");
      counter += 1;
      mermaid
        .render("mermaid-diagram-" + counter, source)
        .then(function (result) {
          el.innerHTML = result.svg;
        })
        .catch(function (err) {
          console.error("Mermaid:", err);
          el.classList.add("mermaid-error");
          el.textContent =
            "Diagramme non rendu : " +
            (err && err.message ? err.message : String(err)) +
            "\n\n" +
            source;
        });
    });
  }

  // Material for MkDocs remplace le contenu sans rechargement complet : il faut
  // rendre à chaque navigation. document$ émet après chaque navigation, mais le
  // premier chargement est déjà passé quand ce script s'exécute.
  renderAll();
  if (typeof document$ !== "undefined") {
    document$.subscribe(renderAll);
  }
})();
