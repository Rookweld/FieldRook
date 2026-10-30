// FieldRook native shell — no-orphan job object + WMI command-line fence.

using System.Diagnostics;
using System.Management;
using System.Runtime.InteropServices;

namespace FieldRook.Backend;

public static class ProcessFence
{
    /// <summary>True when the PID names a live process.</summary>
    public static bool PidAlive(int pid)
    {
        if (pid <= 0)
        {
            return false;
        }

        try
        {
            using var _ = Process.GetProcessById(pid);
            return true;
        }
        catch (Exception)
        {
            return false;
        }
    }

    /// <summary>
    /// Command line of a PID via WMI. Null when unreadable — callers must
    /// treat null as "fence does not hold", never as a match.
    /// </summary>
    public static string? TryGetCommandLine(int pid)
    {
        try
        {
            using var searcher = new ManagementObjectSearcher(
                $"SELECT CommandLine FROM Win32_Process WHERE ProcessId = {pid}");
            foreach (var obj in searcher.Get())
            {
                using (obj)
                {
                    return obj["CommandLine"]?.ToString();
                }
            }

            return null;
        }
        catch (Exception)
        {
            return null;
        }
    }
}

/// <summary>
/// Windows Job Object with KILL_ON_JOB_CLOSE: every assigned child dies
/// with the job's last handle — the shell crashing can never orphan the
/// backend. Assignment failure is non-fatal (nested-job hosts).
/// </summary>
public sealed class JobObject : IDisposable
{
    private const int JobObjectExtendedLimitInformation = 9;
    private const uint KillOnJobClose = 0x2000;

    private nint _handle;
    private bool _disposed;

    public JobObject()
    {
        _handle = NativeMethods.CreateJobObject(nint.Zero, null);
    }

    public bool TryAssign(Process process)
    {
        if (_handle == nint.Zero)
        {
            return false;
        }

        try
        {
            var info = new NativeMethods.JobObjectExtendedLimitInformation
            {
                BasicLimitInformation = new NativeMethods.JobObjectBasicLimitInformation
                {
                    LimitFlags = KillOnJobClose,
                },
            };
            var size = Marshal.SizeOf(info);
            var ptr = Marshal.AllocHGlobal(size);
            try
            {
                Marshal.StructureToPtr(info, ptr, false);
                if (!NativeMethods.SetInformationJobObject(
                        _handle, JobObjectExtendedLimitInformation, ptr, (uint)size))
                {
                    return false;
                }
            }
            finally
            {
                Marshal.FreeHGlobal(ptr);
            }

            return NativeMethods.AssignProcessToJobObject(_handle, process.Handle);
        }
        catch (Exception)
        {
            return false;
        }
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        if (_handle != nint.Zero)
        {
            NativeMethods.CloseHandle(_handle);
            _handle = nint.Zero;
        }
    }
}

internal static partial class NativeMethods
{
    [LibraryImport("kernel32.dll", EntryPoint = "CreateJobObjectW", SetLastError = true, StringMarshalling = StringMarshalling.Utf16)]
    internal static partial nint CreateJobObject(nint attributes, string? name);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static partial bool SetInformationJobObject(
        nint job, int infoType, nint info, uint infoLength);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static partial bool AssignProcessToJobObject(nint job, nint process);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static partial bool CloseHandle(nint handle);

    [StructLayout(LayoutKind.Sequential)]
    internal struct JobObjectBasicLimitInformation
    {
        internal long PerProcessUserTimeLimit;
        internal long PerJobUserTimeLimit;
        internal uint LimitFlags;
        internal nuint MinimumWorkingSetSize;
        internal nuint MaximumWorkingSetSize;
        internal uint ActiveProcessLimit;
        internal nuint Affinity;
        internal uint PriorityClass;
        internal uint SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct IoCounters
    {
        internal ulong ReadOperationCount;
        internal ulong WriteOperationCount;
        internal ulong OtherOperationCount;
        internal ulong ReadTransferCount;
        internal ulong WriteTransferCount;
        internal ulong OtherTransferCount;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct JobObjectExtendedLimitInformation
    {
        internal JobObjectBasicLimitInformation BasicLimitInformation;
        internal IoCounters IoInfo;
        internal nuint ProcessMemoryLimit;
        internal nuint JobMemoryLimit;
        internal nuint PeakProcessMemoryUsed;
        internal nuint PeakJobMemoryUsed;
    }
}
