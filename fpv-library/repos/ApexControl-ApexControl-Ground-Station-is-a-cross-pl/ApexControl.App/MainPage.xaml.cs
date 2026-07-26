using ApexControl.App.ViewModels;

namespace ApexControl.App;

public partial class MainPage : ContentPage
{
    private readonly MainViewModel viewModel;

    public MainPage()
    {
        InitializeComponent();

        viewModel = new MainViewModel();
        BindingContext = viewModel;
    }

    private async void OnConnectClicked(object sender, EventArgs e)
    {
        await viewModel.ConnectAsync();
    }

    private async void OnDisconnectClicked(object sender, EventArgs e)
    {
        await viewModel.DisconnectAsync();
    }

    private async void OnArmClicked(object sender, EventArgs e)
    {
        await viewModel.ArmAsync();
    }

    private async void OnDisarmClicked(object sender, EventArgs e)
    {
        await viewModel.DisarmAsync();
    }

    private async void OnSetGuidedClicked(object sender, EventArgs e)
    {
        await viewModel.SetGuidedModeAsync();
    }

    private async void OnTakeoffClicked(object sender, EventArgs e)
    {
        await viewModel.TakeoffAsync();
    }

}
