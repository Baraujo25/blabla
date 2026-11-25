import AVFoundation
import Foundation

let arguments = Array(CommandLine.arguments.dropFirst())

let semaphore = DispatchSemaphore(value: 0)
var allowed = false
switch AVCaptureDevice.authorizationStatus(for: .audio) {
case .authorized:
    allowed = true
case .notDetermined:
    AVCaptureDevice.requestAccess(for: .audio) { granted in
        allowed = granted
        semaphore.signal()
    }
    _ = semaphore.wait(timeout: .now() + 120)
case .denied, .restricted:
    allowed = false
@unknown default:
    allowed = false
}

if !allowed {
    let alert = Process()
    alert.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
    alert.arguments = [
        "-e",
        "display dialog \"Enable Microphone for BlaBla in System Settings → Privacy & Security → Microphone, then try again.\" buttons {\"OK\"} with title \"BlaBla\"",
    ]
    try? alert.run()
    alert.waitUntilExit()
}

let env = ProcessInfo.processInfo.environment
guard let root = env["BLABLA_ROOT"], !root.isEmpty else {
    fputs("BLABLA_ROOT is not set. Launch BlaBla from scripts/toggle.sh or scripts/blabla.\n", stderr)
    exit(2)
}

guard let python = resolvePython(root: root, env: env) else {
    fputs("Could not find \(root)/.venv/bin/python. Run scripts/setup.sh.\n", stderr)
    exit(1)
}

var subcommand = arguments
if subcommand.isEmpty {
    subcommand = ["toggle"]
}

let logURL = blablaDirectory().appendingPathComponent("blabla.log")
try? FileManager.default.createDirectory(
    at: logURL.deletingLastPathComponent(),
    withIntermediateDirectories: true
)
if !FileManager.default.fileExists(atPath: logURL.path) {
    FileManager.default.createFile(atPath: logURL.path, contents: nil)
}

let proc = Process()
proc.executableURL = URL(fileURLWithPath: python)
proc.arguments = ["-m", "blabla"] + subcommand
proc.environment = env
if let handle = FileHandle(forWritingAtPath: logURL.path) {
    handle.seekToEndOfFile()
    proc.standardOutput = handle
    proc.standardError = handle
}

do {
    try proc.run()
    proc.waitUntilExit()
    exit(proc.terminationStatus)
} catch {
    fputs("Failed to launch blabla: \(error)\n", stderr)
    exit(1)
}

func blablaDirectory() -> URL {
    if let custom = ProcessInfo.processInfo.environment["BLABLA_HOME"], !custom.isEmpty {
        return URL(fileURLWithPath: (custom as NSString).expandingTildeInPath, isDirectory: true)
    }
    return FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".blabla", isDirectory: true)
}

func resolvePython(root: String, env: [String: String]) -> String? {
    if let override = env["BLABLA_PYTHON"], !override.isEmpty,
       FileManager.default.isExecutableFile(atPath: override) {
        return override
    }
    let venv = "\(root)/.venv/bin/python"
    if FileManager.default.isExecutableFile(atPath: venv) {
        return venv
    }
    return nil
}
