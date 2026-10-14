import Foundation

/// Talks to the Python engine's /app/ endpoints (api/flask_server.py).
struct EngineClient: Sendable {
    let baseURL: URL
    let token: String

    static let tokenHeader = "X-Dlwithit-Token"

    struct Failure: LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }

    enum Event: Sendable {
        case snapshot(EngineSnapshot)
        case job(Job)
        case jobRemoved(String)
        case pick(Pick)
        case pickClosed(String)
        case settings(EngineSettings)
    }

    static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

    // MARK: Requests

    func get<T: Decodable>(_ path: String, as type: T.Type = T.self) async throws -> T {
        try await send("GET", path, body: nil)
    }

    @discardableResult
    func post<T: Decodable>(_ path: String, _ body: [String: any Sendable]? = nil, as type: T.Type = T.self) async throws -> T {
        try await send("POST", path, body: body)
    }

    func post(_ path: String, _ body: [String: any Sendable]? = nil) async throws {
        let _: Ignored = try await send("POST", path, body: body)
    }

    func delete(_ path: String) async throws {
        let _: Ignored = try await send("DELETE", path, body: nil)
    }

    func patch<T: Decodable>(_ path: String, _ body: [String: any Sendable], as type: T.Type = T.self) async throws -> T {
        try await send("PATCH", path, body: body)
    }

    private struct Ignored: Decodable {}
    private struct ErrorBody: Decodable { let error: String? }

    private func request(_ method: String, _ path: String) -> URLRequest {
        var req = URLRequest(url: baseURL.appending(path: path))
        req.httpMethod = method
        req.setValue(token, forHTTPHeaderField: Self.tokenHeader)
        return req
    }

    private func send<T: Decodable>(_ method: String, _ path: String, body: [String: any Sendable]?) async throws -> T {
        var req = request(method, path)
        req.timeoutInterval = 60
        if let body {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        let (data, response) = try await URLSession.shared.data(for: req)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(status) else {
            let message = (try? Self.decoder.decode(ErrorBody.self, from: data))?.error
            throw Failure(message: message ?? "The download engine answered \(status).")
        }
        return try Self.decoder.decode(T.self, from: data)
    }

    // MARK: Live events

    /// Server-Sent Events from /app/events. Starts with a full snapshot; ends when the connection drops.
    func events() -> AsyncThrowingStream<Event, Error> {
        var req = request("GET", "app/events")
        req.timeoutInterval = 60 * 60   // keepalives arrive every 15s; this only bounds silence
        let streamRequest = req
        return AsyncThrowingStream { continuation in
            let task = Task { @Sendable in
                do {
                    let (bytes, response) = try await URLSession.shared.bytes(for: streamRequest)
                    guard (response as? HTTPURLResponse)?.statusCode == 200 else {
                        throw Failure(message: "Couldn't subscribe to engine events.")
                    }
                    var eventName = ""
                    for try await line in bytes.lines {
                        if line.hasPrefix("event: ") {
                            eventName = String(line.dropFirst(7))
                        } else if line.hasPrefix("data: ") {
                            // Each event carries exactly one data line (see sse_message()).
                            let data = Data(line.dropFirst(6).utf8)
                            if let event = Self.decodeEvent(eventName, data) {
                                continuation.yield(event)
                            }
                        }
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }

    private struct IDOnly: Decodable { let id: String }

    static func decodeEvent(_ name: String, _ data: Data) -> Event? {
        do {
            switch name {
            case "snapshot": return .snapshot(try decoder.decode(EngineSnapshot.self, from: data))
            case "job": return .job(try decoder.decode(Job.self, from: data))
            case "job_removed": return .jobRemoved(try decoder.decode(IDOnly.self, from: data).id)
            case "pick": return .pick(try decoder.decode(Pick.self, from: data))
            case "pick_closed": return .pickClosed(try decoder.decode(IDOnly.self, from: data).id)
            case "settings": return .settings(try decoder.decode(EngineSettings.self, from: data))
            default: return nil
            }
        } catch {
            engineLog.error("Couldn't decode \(name, privacy: .public) event: \(error.localizedDescription, privacy: .public)")
            return nil
        }
    }
}
