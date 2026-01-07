using System.Threading;
using System.Windows.Forms;

namespace ParkingLotImagesTray;

static class ParkingLotTrayMain
{
    private static Mutex? _mutex;

    /// <summary>
    ///  The main entry point for the application.
    /// </summary>
    [STAThread]
    static void Main()
    {
        const string appGuid = "ParkingLotImagesTray-B4A7-4B1E-9E2C-8C3B5E6D7F8G";
        _mutex = new Mutex(true, appGuid, out bool createdNew);

        if (!createdNew)
        {
            // Another instance is already running
            return;
        }

        try
        {
            // To customize application configuration such as set high DPI settings or default font,
            // see https://aka.ms/applicationconfiguration.
            ApplicationConfiguration.Initialize();
            Application.Run(new TrayApplicationContext());
        }
        finally
        {
            _mutex.ReleaseMutex();
            _mutex.Dispose();
        }
    }    
}