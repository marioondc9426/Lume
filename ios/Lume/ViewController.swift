import UIKit
import WebKit

/// Mostra a interface do Lume. O "servidor" e o lume-backend.js, que responde as chamadas /api/ dentro da propria pagina.
/// A pagina (www) vem dentro do app, mas o app procura uma versao mais nova no GitHub (branch ios-live) ao abrir:
/// se achar, baixa para a pasta do app e avisa; se nao conseguir, avisa tambem.
class ViewController: UIViewController, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler {
    private var web: WKWebView!
    private let nativeVersion = 1   // sobe quando o app nativo muda de um jeito que a pagina nova exige (manifest "min_native")
    private let liveBase = "https://raw.githubusercontent.com/marioondc9426/Lume/ios-live/"
    private var checked = false

    private final class Box { var ok = false; var why = "" }

    // ---------- onde esta a pagina ----------
    private var supportDir: URL { FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0] }
    private var liveDir: URL { supportDir.appendingPathComponent("www-live", isDirectory: true) }
    private var bundleDir: URL? { Bundle.main.url(forResource: "index", withExtension: "html", subdirectory: "www")?.deletingLastPathComponent() }

    private func builtOf(_ dir: URL) -> Int {
        guard let d = try? Data(contentsOf: dir.appendingPathComponent("version.json")),
              let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { return 0 }
        if let n = j["built"] as? Int { return n }
        if let x = j["built"] as? Double { return Int(x) }
        return 0
    }

    /// a pasta baixada vale se for mais nova que a que veio no app
    private func startDir() -> URL? {
        let live = liveDir
        if FileManager.default.fileExists(atPath: live.appendingPathComponent("index.html").path),
           builtOf(live) > (bundleDir.map { builtOf($0) } ?? 0) { return live }
        return bundleDir
    }

    override func loadView() {
        let cfg = WKWebViewConfiguration()
        // a pagina e um arquivo local e precisa falar com as APIs dos provedores (e com o Ollama do PC): libera isso so para este app
        cfg.preferences.setValue(true, forKey: "allowFileAccessFromFileURLs")
        cfg.setValue(true, forKey: "allowUniversalAccessFromFileURLs")
        cfg.allowsInlineMediaPlayback = true
        cfg.userContentController.add(self, name: "lume")
        web = WKWebView(frame: .zero, configuration: cfg)
        web.navigationDelegate = self
        web.uiDelegate = self
        web.isOpaque = false
        web.backgroundColor = UIColor(red: 0.106, green: 0.106, blue: 0.122, alpha: 1)
        web.scrollView.backgroundColor = web.backgroundColor
        web.scrollView.contentInsetAdjustmentBehavior = .never
        web.scrollView.bounces = false
        web.scrollView.alwaysBounceVertical = false
        web.scrollView.alwaysBounceHorizontal = false
        view = web
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        loadStart()
    }

    private func loadStart() {
        if let dir = startDir() {
            web.loadFileURL(dir.appendingPathComponent("index.html"), allowingReadAccessTo: dir)
        } else {
            web.loadHTMLString("<body style='background:#1b1b1f;color:#eee;font-family:-apple-system;padding:24px'><h3>Lume</h3><p>A pasta www nao veio dentro do app.</p></body>", baseURL: nil)
        }
    }

    override var preferredStatusBarStyle: UIStatusBarStyle { .lightContent }

    // ---------- atualizacao ----------
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        if message.name == "lume", let s = message.body as? String, s == "reload" { loadStart() }
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        if !checked {
            checked = true
            DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) { self.checkForUpdate() }
        }
    }

    private func jsString(_ s: String) -> String {
        if let d = try? JSONSerialization.data(withJSONObject: [s]), let t = String(data: d, encoding: .utf8) { return String(t.dropFirst().dropLast()) }
        return "\"\""
    }

    private func notify(_ fn: String, _ text: String) {
        let js = "window.\(fn) && window.\(fn)(\(jsString(text)))"
        DispatchQueue.main.async { self.web.evaluateJavaScript(js, completionHandler: nil) }
    }

    private func checkForUpdate() {
        let curBuilt = startDir().map { builtOf($0) } ?? 0
        guard let url = URL(string: liveBase + "manifest.json?t=\(Int(Date().timeIntervalSince1970))") else { return }
        var req = URLRequest(url: url)
        req.cachePolicy = .reloadIgnoringLocalCacheData
        req.timeoutInterval = 20
        URLSession.shared.dataTask(with: req) { data, resp, err in
            guard err == nil, let http = resp as? HTTPURLResponse, http.statusCode == 200, let data = data,
                  let m = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                self.notify("lumeUpdateFailed", "Não consegui procurar atualização (sem internet ou o GitHub não respondeu). O Lume continua na versão que já está no aparelho.")
                return
            }
            if let minNative = m["min_native"] as? Int, minNative > self.nativeVersion {
                self.notify("lumeUpdateFailed", "Há uma versão nova do Lume, mas ela precisa de um .ipa novo. Instale o .ipa mais recente.")
                return
            }
            let built = (m["built"] as? Int) ?? Int((m["built"] as? Double) ?? 0)
            if built <= curBuilt { return }   // ja esta na ultima
            guard let files = m["files"] as? [[String: Any]] else { return }
            self.download(files: files, version: (m["version"] as? String) ?? "")
        }.resume()
    }

    private func download(files: [[String: Any]], version: String) {
        let fm = FileManager.default
        let tmp = supportDir.appendingPathComponent("www-live-tmp", isDirectory: true)
        try? fm.removeItem(at: tmp)
        do { try fm.createDirectory(at: tmp, withIntermediateDirectories: true) } catch {
            notify("lumeUpdateFailed", "Não consegui atualizar o Lume: sem espaço para guardar os arquivos novos.")
            return
        }
        var items: [(String, Int)] = []
        for f in files {
            guard let p = f["p"] as? String, !p.hasPrefix("/"), !p.contains(".."), let s = f["s"] as? Int else {
                notify("lumeUpdateFailed", "Não consegui atualizar o Lume: a lista de arquivos novos veio estranha.")
                return
            }
            items.append((p, s))
        }
        guard items.contains(where: { $0.0 == "index.html" }) else {
            notify("lumeUpdateFailed", "Não consegui atualizar o Lume: a atualização veio incompleta.")
            return
        }
        DispatchQueue.global(qos: .utility).async {
            for (p, size) in items {
                guard let enc = p.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed), let url = URL(string: self.liveBase + enc) else {
                    try? fm.removeItem(at: tmp)
                    self.notify("lumeUpdateFailed", "Não consegui atualizar o Lume: endereço inválido de \(p).")
                    return
                }
                let box = Box()
                let sem = DispatchSemaphore(value: 0)
                var r = URLRequest(url: url)
                r.timeoutInterval = 30
                r.cachePolicy = .reloadIgnoringLocalCacheData
                URLSession.shared.dataTask(with: r) { d, resp, e in
                    defer { sem.signal() }
                    guard e == nil, let h = resp as? HTTPURLResponse, h.statusCode == 200, let d = d else { box.why = "falha ao baixar \(p)"; return }
                    if d.count != size { box.why = "o arquivo \(p) veio incompleto"; return }
                    let dest = tmp.appendingPathComponent(p)
                    do {
                        try fm.createDirectory(at: dest.deletingLastPathComponent(), withIntermediateDirectories: true)
                        try d.write(to: dest)
                        box.ok = true
                    } catch { box.why = "não consegui gravar \(p)" }
                }.resume()
                sem.wait()
                if !box.ok {
                    try? fm.removeItem(at: tmp)
                    self.notify("lumeUpdateFailed", "Não consegui atualizar o Lume (\(box.why)). O Lume continua na versão que já está no aparelho.")
                    return
                }
            }
            let live = self.liveDir
            try? fm.removeItem(at: live)
            do { try fm.moveItem(at: tmp, to: live) } catch {
                self.notify("lumeUpdateFailed", "Não consegui atualizar o Lume: não deu para instalar os arquivos novos.")
                return
            }
            self.notify("lumeUpdateReady", version)
        }
    }

    // ---------- links, janelas e alertas ----------
    // links externos (http/https) abrem no Safari; a pagina do app continua onde esta
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if navigationAction.navigationType == .linkActivated, let url = navigationAction.request.url, url.scheme == "http" || url.scheme == "https" {
            UIApplication.shared.open(url)
            decisionHandler(.cancel)
        } else {
            decisionHandler(.allow)
        }
    }

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = navigationAction.request.url, url.scheme == "http" || url.scheme == "https" { UIApplication.shared.open(url) }
        return nil
    }

    // alert / confirm / prompt do JavaScript
    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let a = UIAlertController(title: nil, message: message, preferredStyle: .alert)
        a.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler() })
        present(a, animated: true)
    }

    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let a = UIAlertController(title: nil, message: message, preferredStyle: .alert)
        a.addAction(UIAlertAction(title: "Cancelar", style: .cancel) { _ in completionHandler(false) })
        a.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler(true) })
        present(a, animated: true)
    }

    func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
        let a = UIAlertController(title: nil, message: prompt, preferredStyle: .alert)
        a.addTextField { $0.text = defaultText }
        a.addAction(UIAlertAction(title: "Cancelar", style: .cancel) { _ in completionHandler(nil) })
        a.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler(a.textFields?.first?.text) })
        present(a, animated: true)
    }
}
