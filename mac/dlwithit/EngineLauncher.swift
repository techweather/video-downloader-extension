import Foundation
import os

let engineLog = Logger(subsystem: "com.dlwithit.app", category: "engine")

/// Finds a running dlwithit engine on 127.0.0.1:5555, or starts one.
///
/// Where the engine comes from:
///  • Shipped app: an `engine/dlwithit-engine` executable inside the app's Resources
///    (built by PyInstaller — not wired up yet).
///  • Development: this repo's `.venv` Python running `engine_main.py`, located from
///    this source file's own path, so a debug build from Xcode just works.
@MainActor
final class EngineLauncher {
    enum Outcome {
        case connected(EngineClient)
        case otherAppRunning        // the old Qt dlwithit holds the port
        case failed(String)
    }

    static let port = 5555
    private(set) var process: Process?
    private let baseURL = URL(string: "http://127.0.0.1:\(EngineLauncher.port)/")!

    private struct Health: Decodable { let engine: Bool? }
    private struct EngineInfo: Decodable { let port: Int; let token: String }

    func connect() async -> Outcome {
        if let health = await health() {
            if health.engine == true, let info = Self.readEngineInfo() {
                engineLog.info("Attaching to the engine that's already running")
                return .connected(EngineClient(baseURL: baseURL, token: info.token))
            }
            return health.engine == true
                ? .failed("A dlwithit engine is running but its details file is missing. Quit dlwithit and try again.")
                : .otherAppRunning
        }
        return await launch()
    }

    /// Ask an engine we started to stop. Engines we merely attached to are left running.
    func stopIfOwned(client: EngineClient?) {
        guard let process, process.isRunning else { return }
        if let client {
            var req = URLRequest(url: client.baseURL.appending(path: "app/shutdown"))
            req.httpMethod = "POST"
            req.setValue(client.token, forHTTPHeaderField: EngineClient.tokenHeader)
            req.timeoutInterval = 1
            // Synchronous on purpose: the app is quitting.
            let done = DispatchSemaphore(value: 0)
            URLSession.shared.dataTask(with: req) { _, _, _ in done.signal() }.resume()
            _ = done.wait(timeout: .now() + 1.5)
        }
        if process.isRunning { process.terminate() }
    }

    // MARK: - Private

    private func health() async -> Health? {
        var req = URLRequest(url: baseURL.appending(path: "health"))
        req.timeoutInterval = 1
        guard let (data, response) = try? await URLSession.shared.data(for: req),
              (response as? HTTPURLResponse)?.statusCode == 200 else { return nil }
        return try? JSONDecoder().decode(Health.self, from: data)
    }

    private static var supportDir: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appending(path: "dlwithit", directoryHint: .isDirectory)
    }

    private static func readEngineInfo() -> EngineInfo? {
        guard let data = try? Data(contentsOf: supportDir.appending(path: "engine.json")) else { return nil }
        return try? JSONDecoder().decode(EngineInfo.self, from: data)
    }

    /// The command that starts the engine, or nil if neither a bundled nor a dev engine exists.
    private static func engineCommand() -> (executable: URL, arguments: [String], directory: URL)? {
        if let bundled = Bundle.main.resourceURL?.appending(path: "engine/dlwithit-engine"),
           FileManager.default.isExecutableFile(atPath: bundled.path) {
            return (bundled, [], bundled.deletingLastPathComponent())
        }
        // #filePath is this file's location at build time: <repo>/mac/dlwithit/EngineLauncher.swift
        let repo = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let python = repo.appending(path: ".venv/bin/python3.12")
        let script = repo.appending(path: "engine_main.py")
        guard FileManager.default.isExecutableFile(atPath: python.path),
              FileManager.default.fileExists(atPath: script.path) else { return nil }
        return (python, [script.path], repo)
    }

    private func launch() async -> Outcome {
        guard let command = Self.engineCommand() else {
            return .failed("Couldn't find the download engine. In development, the repo needs its .venv (see CLAUDE.md).")
        }
        let token = UUID().uuidString + UUID().uuidString
        let process = Process()
        process.executableURL = command.executable
        process.arguments = command.arguments + ["--parent-pid", String(ProcessInfo.processInfo.processIdentifier)]
        process.currentDirectoryURL = command.directory
        var env = ProcessInfo.processInfo.environment
        env["DLWITHIT_TOKEN"] = token
        env["PYTHONUNBUFFERED"] = "1"
        // GUI apps get a minimal PATH; add Homebrew so a dev engine finds ffmpeg and deno.
        env["PATH"] = ["/opt/homebrew/bin", "/usr/local/bin", env["PATH"] ?? "/usr/bin:/bin"].joined(separator: ":")
        process.environment = env

        try? FileManager.default.createDirectory(at: Self.supportDir, withIntermediateDirectories: true)
        let logURL = Self.supportDir.appending(path: "engine.log")
        FileManager.default.createFile(atPath: logURL.path, contents: nil)
        if let log = try? FileHandle(forWritingTo: logURL) {
            process.standardOutput = log
            process.standardError = log
        }

        do {
            try process.run()
        } catch {
            return .failed("Couldn't start the download engine: \(error.localizedDescription)")
        }
        self.process = process
        engineLog.info("Started engine, pid \(process.processIdentifier)")

        // Python + yt-dlp take a moment to import.
        for _ in 0..<60 {
            try? await Task.sleep(for: .milliseconds(250))
            if !process.isRunning {
                return .failed("The download engine stopped while starting. Details are in ~/Library/Application Support/dlwithit/engine.log.")
            }
            if let health = await health(), health.engine == true {
                return .connected(EngineClient(baseURL: baseURL, token: token))
            }
        }
        process.terminate()
        return .failed("The download engine took too long to start.")
    }
}
