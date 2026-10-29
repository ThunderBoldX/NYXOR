#import <UIKit/UIKit.h>
#import <WebKit/WebKit.h>
#import "PythonEngine.h"
#import "DropSession.h"

@interface MinerController : UIViewController <WKScriptMessageHandler, WKNavigationDelegate>
@property(nonatomic, strong) WKWebView *web;
@property(nonatomic, strong) dispatch_queue_t engineQueue;
@property(nonatomic, strong) NSURL *frontend;
@property BOOL active;
@property(nonatomic, strong) DropSession *dropSession;
- (void)suspend;
- (void)resume;
@end

@implementation MinerController
- (void)viewDidLoad {
    [super viewDidLoad];
    self.active = YES;
    self.engineQueue = dispatch_queue_create("com.thunderboldx.nyxor.engine", DISPATCH_QUEUE_SERIAL);
    self.dropSession = [[DropSession alloc] initWithQueue:self.engineQueue];
    self.view.backgroundColor = [UIColor colorWithRed:12/255.0 green:11/255.0 blue:16/255.0 alpha:1];
    WKWebViewConfiguration *configuration = [WKWebViewConfiguration new];
    [configuration.userContentController addScriptMessageHandler:self name:@"nyxor"];
    NSString *bridge = @"window.NyxorNative={platform:'ios',request:(id,payload)=>window.webkit.messageHandlers.nyxor.postMessage({id,payload}),haptic:()=>window.webkit.messageHandlers.nyxor.postMessage({haptic:true})};";
    [configuration.userContentController addUserScript:[[WKUserScript alloc] initWithSource:bridge injectionTime:WKUserScriptInjectionTimeAtDocumentStart forMainFrameOnly:YES]];
    self.web = [[WKWebView alloc] initWithFrame:CGRectZero configuration:configuration];
    self.web.navigationDelegate = self;
    self.web.opaque = NO;
    self.web.backgroundColor = self.view.backgroundColor;
    self.web.scrollView.backgroundColor = self.view.backgroundColor;
    self.web.scrollView.contentInsetAdjustmentBehavior = UIScrollViewContentInsetAdjustmentNever;
    self.web.translatesAutoresizingMaskIntoConstraints = NO;
    [self.view addSubview:self.web];
    UILayoutGuide *safe = self.view.safeAreaLayoutGuide;
    [NSLayoutConstraint activateConstraints:@[[self.web.topAnchor constraintEqualToAnchor:safe.topAnchor], [self.web.bottomAnchor constraintEqualToAnchor:safe.bottomAnchor], [self.web.leadingAnchor constraintEqualToAnchor:safe.leadingAnchor], [self.web.trailingAnchor constraintEqualToAnchor:safe.trailingAnchor]]];
    self.frontend = [NSBundle.mainBundle URLForResource:@"frontend" withExtension:nil];
    [self.web loadFileURL:[self.frontend URLByAppendingPathComponent:@"index.html"] allowingReadAccessToURL:self.frontend];
}
- (void)reply:(NSString *)identity value:(NSDictionary *)value {
    if ([value[@"data"] isKindOfClass:NSDictionary.class] && value[@"data"][@"settings"]) {
        NSMutableDictionary *copy = [value mutableCopy], *data = [value[@"data"] mutableCopy];
        data[@"ios_background"] = [self.dropSession status]; copy[@"data"] = data; value = copy;
    }
    NSData *encoded = [NSJSONSerialization dataWithJSONObject:@[identity, value] options:0 error:nil];
    NSString *json = [[NSString alloc] initWithData:encoded encoding:NSUTF8StringEncoding];
    [self.web evaluateJavaScript:[NSString stringWithFormat:@"window.nativeReply(...%@)",json] completionHandler:nil];
}
- (void)userContentController:(WKUserContentController *)controller didReceiveScriptMessage:(WKScriptMessage *)message {
    if (!message.frameInfo.mainFrame || ![message.frameInfo.request.URL isFileURL] ||
        ![message.frameInfo.request.URL.path hasPrefix:[self.frontend.path stringByAppendingString:@"/"]]) return;
    if (![message.body isKindOfClass:NSDictionary.class]) return;
    NSDictionary *body = message.body;
    if ([body[@"haptic"] boolValue]) { [[[UISelectionFeedbackGenerator alloc] init] selectionChanged]; return; }
    NSString *identity = body[@"id"], *payload = body[@"payload"];
    if (![identity isKindOfClass:NSString.class] || ![payload isKindOfClass:NSString.class] || payload.length > 64000) return;
    NSDictionary *request = [NSJSONSerialization JSONObjectWithData:[payload dataUsingEncoding:NSUTF8StringEncoding] options:0 error:nil];
    if (![request isKindOfClass:NSDictionary.class]) return;
    NSString *action = request[@"action"];
    if (![action isKindOfClass:NSString.class]) {
        [self reply:identity value:@{@"ok":@NO,@"error":@"Invalid action"}]; return;
    }
    if ([action hasPrefix:@"ios_"] && ![action isEqual:@"ios_background_begin"] && ![action isEqual:@"ios_background_cancel"]) {
        [self reply:identity value:@{@"ok":@NO,@"error":@"Native lifecycle action only"}]; return;
    }
    if ([action isEqual:@"ios_background_begin"]) {
        NSString *drop = request[@"drop_id"];
        if (!self.active || ![drop isKindOfClass:NSString.class] || drop.length > 200) {
            [self reply:identity value:@{@"ok":@NO,@"error":@"Select a Drop while NYXOR is open"}]; return;
        }
        [self.dropSession begin:drop completion:^(NSDictionary *result) {[self reply:identity value:result];}]; return;
    }
    if ([action isEqual:@"ios_background_cancel"]) {
        [self.dropSession cancel]; [self reply:identity value:@{@"ok":@YES,@"data":@{}}]; return;
    }
    NSSet *publicActions = [NSSet setWithArray:@[@"snapshot",@"check_connection",@"start",@"stop",@"restart",@"auth",@"logout",@"queue",@"streamers",@"points_games",@"settings",@"directory",@"search",@"delete_history",@"account_select",@"account_add",@"account_delete",@"copy_code",@"open"]];
    if (![publicActions containsObject:action]) {
        [self reply:identity value:@{@"ok":@NO,@"error":@"Unknown action"}]; return;
    }
    if ([action isEqual:@"open"]) {
        NSURL *url = [request[@"url"] isKindOfClass:NSString.class] ? [NSURL URLWithString:request[@"url"]] : nil;
        NSSet *hosts = [NSSet setWithArray:@[@"twitch.tv",@"www.twitch.tv",@"id.twitch.tv"]];
        if (![url.scheme isEqual:@"https"] || ![hosts containsObject:url.host.lowercaseString] || url.user || url.password || (url.port && url.port.integerValue != 443)) {
            [self reply:identity value:@{@"ok":@NO,@"error":@"Only secure Twitch links are allowed"}]; return;
        }
        [UIApplication.sharedApplication openURL:url options:@{} completionHandler:^(BOOL success) {
            [self reply:identity value:success ? @{@"ok":@YES,@"data":@{}} : @{@"ok":@NO,@"error":@"Could not open Twitch"}];
        }]; return;
    }
    if (!self.active && ([action isEqual:@"start"] || [action isEqual:@"restart"])) {
        [self reply:identity value:@{@"ok":@NO,@"error":@"Return to NYXOR to start farming"}]; return;
    }
    dispatch_async(self.engineQueue, ^{
        NSString *query = payload;
        if ([action isEqual:@"copy_code"]) query = @"{\"action\":\"snapshot\"}";
        NSDictionary *response = [NSJSONSerialization JSONObjectWithData:[[PythonEngine request:query] dataUsingEncoding:NSUTF8StringEncoding] options:0 error:nil];
        dispatch_async(dispatch_get_main_queue(), ^{
            if ([action isEqual:@"copy_code"] && [response[@"ok"] boolValue]) {
                NSString *code = response[@"data"][@"auth"][@"code"];
                if ([code isKindOfClass:NSString.class]) UIPasteboard.generalPasteboard.string = code;
            }
            [self reply:identity value:response ?: @{@"ok":@NO,@"error":@"Invalid miner response"}];
        });
    });
}
- (void)webView:(WKWebView *)webView decidePolicyForNavigationAction:(WKNavigationAction *)action decisionHandler:(void (^)(WKNavigationActionPolicy))decisionHandler {
    NSURL *url = action.request.URL;
    BOOL local = url.isFileURL && [url.path hasPrefix:[self.frontend.path stringByAppendingString:@"/"]];
    decisionHandler(local ? WKNavigationActionPolicyAllow : WKNavigationActionPolicyCancel);
}
- (void)suspend {
    self.active = NO;
    __block UIBackgroundTaskIdentifier token = UIBackgroundTaskInvalid;
    void (^finish)(void) = ^{
        if (token != UIBackgroundTaskInvalid) {
            [UIApplication.sharedApplication endBackgroundTask:token];
            token = UIBackgroundTaskInvalid;
        }
    };
    token = [UIApplication.sharedApplication beginBackgroundTaskWithName:@"Save farming session" expirationHandler:finish];
    dispatch_async(self.engineQueue, ^{
        [PythonEngine request:@"{\"action\":\"ios_suspend\"}"];
        dispatch_async(dispatch_get_main_queue(), finish);
    });
}
- (void)resume {
    self.active = YES;
    dispatch_async(self.engineQueue, ^{
        [PythonEngine request:@"{\"action\":\"ios_resume\"}"];
        dispatch_async(dispatch_get_main_queue(), ^{[self.web evaluateJavaScript:@"typeof refresh==='function'&&refresh(true)" completionHandler:nil];});
    });
}
@end

@interface AppDelegate : UIResponder <UIApplicationDelegate>
@property(nonatomic, strong) UIWindow *window;
@property(nonatomic, strong) MinerController *miner;
@end
@implementation AppDelegate
- (BOOL)application:(UIApplication *)application didFinishLaunchingWithOptions:(NSDictionary *)options {
    self.window = [[UIWindow alloc] initWithFrame:UIScreen.mainScreen.bounds];
    self.miner = [MinerController new]; [self.miner loadViewIfNeeded]; self.window.rootViewController = self.miner;
    [self.window makeKeyAndVisible]; return YES;
}
- (void)applicationDidEnterBackground:(UIApplication *)application { [self.miner suspend]; }
- (void)applicationWillEnterForeground:(UIApplication *)application { [self.miner resume]; }
@end
int main(int argc, char *argv[]) { @autoreleasepool { return UIApplicationMain(argc, argv, nil, NSStringFromClass(AppDelegate.class)); } }
