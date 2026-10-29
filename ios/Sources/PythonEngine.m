#import "PythonEngine.h"
#include <Python/Python.h>

@implementation PythonEngine
+ (NSString *)request:(NSString *)payload {
    // Called only by the controller's serial queue. The asyncio worker owns
    // shared application state; the GIL is released while waiting for it.
    static PyObject *requestFunction = NULL;
    static NSString *startupError = nil;
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        NSString *bundle = NSBundle.mainBundle.resourcePath;
        NSString *home = [bundle stringByAppendingPathComponent:@"python"];
        NSString *search = [NSString stringWithFormat:@"%@/python/lib/python3.13:%@/python/lib/python3.13/lib-dynload:%@/core:%@/vendor", bundle, bundle, bundle, bundle];
        setenv("PYTHONHOME", home.UTF8String, 1);
        setenv("PYTHONPATH", search.UTF8String, 1);
        setenv("NYXOR_PLATFORM", "ios", 1);
        setenv("SSL_CERT_FILE", [[bundle stringByAppendingPathComponent:@"vendor/certifi/cacert.pem"] UTF8String], 1);
        PyPreConfig pre;
        PyPreConfig_InitPythonConfig(&pre);
        pre.utf8_mode = 1;
        PyStatus status = Py_PreInitialize(&pre);
        if (PyStatus_Exception(status)) { startupError = @"Python pre-initialization failed"; return; }
        PyConfig config;
        PyConfig_InitPythonConfig(&config);
        config.buffered_stdio = 0;
        config.write_bytecode = 0;
        config.install_signal_handlers = 0;
        status = Py_InitializeFromConfig(&config);
        PyConfig_Clear(&config);
        if (PyStatus_Exception(status)) { startupError = @"Python initialization failed"; return; }
        NSString *data = [NSSearchPathForDirectoriesInDomains(NSApplicationSupportDirectory, NSUserDomainMask, YES).firstObject stringByAppendingPathComponent:@"NYXOR"];
        [NSFileManager.defaultManager createDirectoryAtPath:data withIntermediateDirectories:YES attributes:@{NSFileProtectionKey:NSFileProtectionCompleteUntilFirstUserAuthentication} error:nil];
        NSURL *dataURL = [NSURL fileURLWithPath:data];
        [dataURL setResourceValue:@YES forKey:NSURLIsExcludedFromBackupKey error:nil];
        NSString *locales = [data stringByAppendingPathComponent:@"locales"];
        [NSFileManager.defaultManager createDirectoryAtPath:locales withIntermediateDirectories:YES attributes:nil error:nil];
        for (NSString *name in @[@"en.json",@"uk.json"]) {
            NSString *source = [bundle stringByAppendingPathComponent:[@"core/nyxor/locales" stringByAppendingPathComponent:name]];
            NSData *locale = [NSData dataWithContentsOfFile:source];
            if (!locale || ![locale writeToFile:[locales stringByAppendingPathComponent:name] atomically:YES]) {
                startupError = @"Could not prepare translations"; PyEval_SaveThread(); return;
            }
        }
        PyObject *module = PyImport_ImportModule("nyxor.ios_runtime");
        if (module) {
            PyObject *result = PyObject_CallMethod(module, "initialize", "s", data.UTF8String);
            if (result) {
                Py_DECREF(result);
                PyObject *worker = PyImport_ImportModule("nyxor.worker.runtime");
                if (worker) { Py_DECREF(worker); requestFunction = PyObject_GetAttrString(module, "request"); }
            }
            Py_DECREF(module);
        }
        if (!requestFunction) { PyErr_Print(); startupError = @"Could not load the embedded miner. Check the iOS build log."; }
        PyEval_SaveThread();
    });
    if (startupError) {
        NSData *json = [NSJSONSerialization dataWithJSONObject:@{@"ok":@NO,@"error":startupError} options:0 error:nil];
        return [[NSString alloc] initWithData:json encoding:NSUTF8StringEncoding];
    }
    PyGILState_STATE gil = PyGILState_Ensure();
    PyObject *result = PyObject_CallFunction(requestFunction, "s", payload.UTF8String);
    NSString *response = nil;
    if (result) { const char *value = PyUnicode_AsUTF8(result); if (value) response = [NSString stringWithUTF8String:value]; Py_DECREF(result); }
    if (!response) PyErr_Print();
    PyGILState_Release(gil);
    if (response) {
        NSDictionary *value = [NSJSONSerialization JSONObjectWithData:[response dataUsingEncoding:NSUTF8StringEncoding] options:0 error:nil];
        if ([value[@"ok"] boolValue]) {
            NSString *path = [NSSearchPathForDirectoriesInDomains(NSApplicationSupportDirectory, NSUserDomainMask, YES).firstObject stringByAppendingPathComponent:@"NYXOR/ios-ready.json"];
            if (![NSFileManager.defaultManager fileExistsAtPath:path]) [@"{\"ok\":true}" writeToFile:path atomically:YES encoding:NSUTF8StringEncoding error:nil];
        }
    }
    return response ?: @"{\"ok\":false,\"error\":\"Embedded miner request failed\"}";
}
@end
