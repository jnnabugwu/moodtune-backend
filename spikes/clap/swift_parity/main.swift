// Parity harness: runs the app's AudioWindowDecoder on macOS.
//   decode <audio file> <output dir>
// Writes window_<i>.f32 (raw little-endian float32, 16 kHz mono) + meta.json.
import Foundation

let args = CommandLine.arguments
guard args.count == 3 else {
  FileHandle.standardError.write("usage: decode <audio file> <output dir>\n".data(using: .utf8)!)
  exit(2)
}
let outDir = URL(fileURLWithPath: args[2], isDirectory: true)
try FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)

do {
  let start = Date()
  let decoded = try AudioWindowDecoder(targetSampleRate: 16_000).decode(
    url: URL(fileURLWithPath: args[1]), positions: [0.25, 0.5, 0.75], windowSeconds: 10)
  let elapsedMs = Date().timeIntervalSince(start) * 1000
  for (i, window) in decoded.windows.enumerated() {
    let data = window.withUnsafeBufferPointer { Data(buffer: $0) }
    try data.write(to: outDir.appendingPathComponent("window_\(i).f32"))
  }
  let meta: [String: Any] = [
    "startSeconds": decoded.startSeconds, "durationSeconds": decoded.durationSeconds,
    "sourceSampleRate": decoded.sourceSampleRate, "channelCount": decoded.channelCount,
    "elapsedMs": elapsedMs,
  ]
  try JSONSerialization.data(withJSONObject: meta).write(to: outDir.appendingPathComponent("meta.json"))
} catch let error as AudioWindowDecoder.DecodeError {
  try JSONSerialization.data(withJSONObject: ["error": error.code, "message": error.message])
    .write(to: outDir.appendingPathComponent("meta.json"))
}
